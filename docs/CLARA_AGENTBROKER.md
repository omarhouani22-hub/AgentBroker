# Clara and AgentBroker

Clara is the private conversational interface to AgentBroker. The first tool
bridge supports local reads in the existing conversation and history:

- `/agent status` or `Show AgentBroker status`: report installed internal runtimes.
- `/agent search Basil` or `Search my uploaded files: Basil`: retrieve excerpts
  from private uploads and the latest 200 saved knowledge entries.

Search returns verbatim, unverified excerpts and their file/knowledge locators.
It does not synthesize a researched answer. Matching is lexical and bounded;
absence of a match does not establish absence from every saved record.
Both commands bypass inference, external providers and daily model quotas.
The existing application authentication protects this conversation and its tools.
Ordinary messages still use the configured conversation model. The tool parser
is deliberately narrow; there is no general language-to-action planner yet.

This bridge does not run research, publish, modify code, train model weights or
launch background experiments. Those AgentBroker pathways have different
execution/provider requirements and are not wired into private chat here.
Installing a runtime does not prove answer quality, microphone performance or
playback on the owner's device.

Validation: private-file and saved-knowledge retrieval through the conversation
endpoint; persistence in conversation history; model-independent status; honest
no-match output; ordinary/unsupported messages cannot select tool operations.
