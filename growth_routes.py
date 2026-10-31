"""Owner-only Growth Manager API; public policy answers contain no CRM data."""
import json
import time
from flask import jsonify, request, render_template
import growth_manager as growth


def install_routes(app, db):
    @app.errorhandler(growth.GrowthError)
    def growth_error(error):
        return jsonify(error=error.message), error.code

    @app.after_request
    def growth_headers(response):
        if request.path.startswith(('/growth/', '/command-center/', '/agentvault/advice')):
            response.headers['Cache-Control'] = 'no-store'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['Referrer-Policy'] = 'no-referrer'
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        return response

    def body():
        data = request.get_json(silent=True)
        if not isinstance(data, dict): raise growth.GrowthError('Supply a JSON object')
        return data

    @app.get('/command-center/growth')
    def growth_dashboard():
        return render_template('growth.html')

    @app.get('/growth/status')
    def growth_status():
        growth.setup(db)
        growth.daily_report(db, int(time.time()))
        return jsonify(growth.snapshot(db))

    @app.post('/growth/settings')
    def growth_settings():
        data = body()
        if (set(data) != {'enabled', 'sources'} or type(data['enabled']) is not bool or not isinstance(data['sources'], list)
                or any(source not in growth.SOURCES for source in data['sources']) or len(data['sources']) != len(set(data['sources']))
                or (data['enabled'] and not data['sources'])):
            raise growth.GrowthError('Choose enabled and permitted public sources')
        growth.setup(db)
        with db() as c: c.execute('UPDATE growth_settings SET config=?,next_scan=0 WHERE id=1', (json.dumps(data),))
        if not app.testing: growth.start_worker(db)
        return jsonify(saved=True, external_publishing=False)

    @app.post('/growth/run')
    def growth_run():
        result = growth.tick(db)
        growth.daily_report(db, int(time.time()), refresh=True)
        return jsonify(result)

    @app.post('/growth/policies/<identity>/review')
    def growth_policy_review(identity):
        data = body()
        if set(data) != {'action'} or data['action'] not in ('approve', 'revoke'): raise growth.GrowthError('Choose approve or revoke')
        growth.setup(db)
        if identity != growth.POLICY_ID: raise growth.GrowthError('Unknown policy version', 404)
        with db() as c: c.execute('UPDATE growth_policies SET state=? WHERE id=?', ('approved' if data['action'] == 'approve' else 'pending', identity))
        identity = growth.action_begin(db, 'owner_policy_review', {'policy_id': identity, 'decision': data['action']})
        growth.action_end(db, identity, 'completed', {'owner_action': True})
        return jsonify(saved=True)

    @app.post('/growth/leads/<identity>')
    def growth_lead_update(identity):
        growth.setup(db); growth.update_lead(db, identity, body())
        growth.daily_report(db, int(time.time()), refresh=True)
        return jsonify(saved=True)

    @app.post('/growth/drafts/<identity>/review')
    def growth_draft_review(identity):
        data = body()
        if set(data) != {'action', 'digest'}: raise growth.GrowthError('Supply decision and reviewed digest')
        growth.setup(db); growth.review_draft(db, identity, data['action'], data['digest'])
        return jsonify(saved=True, published=False)

    @app.post('/growth/leads/<identity>/demo')
    def growth_synthetic_demo(identity):
        if body(): raise growth.GrowthError('The demo accepts no customer input; synthetic state only')
        growth.setup(db)
        return jsonify(growth.synthetic_demo(db,identity))

    @app.post('/growth/drafts/<identity>/edit')
    def growth_draft_edit(identity):
        data = body()
        if set(data) != {'content'}: raise growth.GrowthError('Supply draft content only')
        growth.setup(db)
        return jsonify(id=growth.edit_draft(db, identity, data['content']), approved=False)

    @app.post('/growth/drafts/<identity>/publish')
    def growth_draft_publish(identity):
        data = body()
        if set(data) != {'digest', 'confirm'} or data['confirm'] != 'publish-this-exact-draft': raise growth.GrowthError('Confirm this exact approved draft')
        growth.setup(db)
        return jsonify(growth.publish(db, identity, data['digest']))

    @app.post('/growth/drafts/<identity>/post')
    def growth_post_draft(identity):
        data = body()
        if set(data) != {'submolt'} or data['submolt'] != 'general': raise growth.GrowthError('Only the existing general Moltbook destination is supported')
        growth.setup(db)
        with db() as c: row = c.execute('SELECT lead_id,payload FROM growth_drafts WHERE id=?', (identity,)).fetchone()
        if not row: raise growth.GrowthError('Unknown draft', 404)
        payload = json.loads(row[1]); payload.update(kind='educational_post', platform='moltbook', target_id='general', title='A bounded restore test for agent state')
        return jsonify(id=growth.add_draft(db, row[0], payload, growth.POLICY_ID, int(time.time())), approved=False)

    @app.post('/growth/receipts/<source>')
    def growth_receipt(source):
        if len(request.get_data()) > 4096: raise growth.GrowthError('Receipt too large', 413)
        growth.setup(db)
        result = growth.receive_receipt(db, source, request.get_data(), request.headers.get('X-Growth-Signature'))
        growth.daily_report(db, int(time.time()), refresh=True)
        return jsonify(result)

    @app.post('/agentvault/advice')
    def growth_customer_advice():
        data = body()
        if set(data) != {'topic'} or not isinstance(data['topic'],str) or data['topic'] not in growth.POLICY: raise growth.GrowthError('Choose a documented product topic; do not enter personal data or credentials')
        growth.setup(db)
        with db() as c: row = c.execute('SELECT state FROM growth_policies WHERE id=?', (growth.POLICY_ID,)).fetchone()
        if not row or row[0] != 'approved': raise growth.GrowthError('Product answers await owner policy approval', 503)
        return jsonify(answer=growth.POLICY[data['topic']], policy_version=growth.POLICY_ID,
                       generated_by='approved_documentation_lookup', sales_enabled=False, tools_executed=False)

    if not app.testing: growth.start_worker(db)
