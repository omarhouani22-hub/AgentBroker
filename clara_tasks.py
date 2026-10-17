"""Bounded content preparation. No external account actions or video-render claims."""
import re
from datetime import datetime, timezone

TASKS = ('chat', 'youtube_video', 'facebook_page')
CAPABILITIES = {
    'youtube_video': {'preparation': True, 'video_rendering': False, 'publishing': False},
    'facebook_page': {'copy_preparation': True, 'page_creation': False, 'publishing': False},
}

def infer_task(text):
    text = text.lower()
    if not re.search(r'\b(create|make|prepare|draft|build|write)\b|اعم[للي]|جهز|حض[رري]|انش[ئي]|اكتب', text):
        return 'chat'
    if re.search(r'youtube|يوتيوب|يوتيوب', text) and re.search(r'video|short|فيديو|شورت', text):
        return 'youtube_video'
    if re.search(r'facebook|فيسبوك|فيس بوك', text) and re.search(r'page|صفحة|صفحه', text):
        return 'facebook_page'
    return 'chat'

def context(task):
    if task not in TASKS:
        raise ValueError('Choose a supported content task')
    shared = ('This runtime can prepare a downloadable text draft only. Do not claim a video file was rendered, '
              'a Facebook page/account was created, anything was uploaded/published/scheduled, or tools were connected. '
              'No video-rendering or social publishing connector is configured here. Explain that limitation briefly. '
              'Use the owner\'s message language and stay within 1900 characters. Mark factual claims requiring verification; '
              'do not claim research without supplied evidence. ')
    if task == 'youtube_video':
        return shared + ('Prepare a practical YouTube production package: title, hook, short original voiceover/script '
                         '(default 30–60 seconds), timed shot list, visual prompts, description and next production steps. '
                         'If the topic is missing, ask for the topic rather than inventing the owner\'s objective. '
                         'Clearly label the result a script/production plan, not a finished video.')
    if task == 'facebook_page':
        return shared + ('Prepare a Facebook page launch package: suggested page name, category, short bio, '
                         'cover/profile visual brief, three starter post drafts, and account connection/setup steps. '
                         'If business or audience is missing, ask a focused question. Clearly label it a draft page package, '
                         'not a created Facebook page.')
    return ''

def save_draft(db, task, content):
    if task not in TASKS or task == 'chat':
        return None
    from clara_documents import parse_document, store
    name = task + '_draft_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S') + '.txt'
    data = content.encode('utf-8')
    identity = store(db, name, data, parse_document(name, data))
    return {'download': '/companion/files/' + identity + '/download',
            'download_label': 'Download video production draft' if task == 'youtube_video' else 'Download Facebook page draft',
            'artifact_kind': 'content_draft', 'content_task': task, 'capabilities': CAPABILITIES[task]}
