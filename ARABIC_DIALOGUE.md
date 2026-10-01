# Arabic dialogue refinement

Private dialogue resolves auto language from the latest meaningful user turn,
including Arabic questions containing English product names. Explicit owner
language selection wins. Replies must pass a script-based language check.
A wrong-language free reply gets one repair attempt through `openrouter/free`
only, within a shared 110-second request budget. Quota and provider failures
are not retried. Experimental local replies still fall back to the free router.

The private prompt asks for direct answers, clear everyday Arabic, contextual
handling of short acceptances, and at most one useful follow-up question. It
distinguishes proposed actions from completed work. Prompt changes cannot
guarantee semantic correctness or improve the underlying model weights.

Private memory overlap normalizes Arabic diacritics, tatweel, alef variants and
alef maqsura, and filters common Arabic/English words. This is lexical retrieval,
not semantic embedding or unrestricted autobiographical memory. Public
Moltbook requests never receive this private context.

On the first health check in each process, `dialogue_quality.py` runs three fixed
public fixtures on the same free router: Arabic explanation, a synthetic Arabic
memory item, and a switch to English. At most six provider requests occur if
all need language repair. Health reports only aggregate fixture results, no
private prompts or generated text. The check runs in a background thread and
never publishes a post, modifies preferences, changes weights, or promotes a
model. Script/fixture success is a smoke check; human semantic review remains
required. It does not prove a general intelligence gain or a before/after gain.

Validation: 60 focused mocked tests pass. Production fixture results are
reported separately by `/health` after deployment.
