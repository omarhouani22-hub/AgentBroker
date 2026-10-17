import Foundation

func url(_ value: String) -> URL? { URL(string: value) }
precondition(ClaraURLPolicy.trusted(ClaraURLPolicy.home))
precondition(ClaraURLPolicy.trusted(url("https://agentbroker-jayk.onrender.com:443/clara/")))
for value in ["http://agentbroker-jayk.onrender.com/clara/", "https://agentbroker-jayk.onrender.com.evil.example/clara/", "https://agentbroker-jayk.onrender.com:444/clara/", "https://user:secret@agentbroker-jayk.onrender.com/clara/", "file:///clara/", "javascript:alert(1)"] {
    precondition(!ClaraURLPolicy.trusted(url(value)), value)
}
precondition(ClaraURLPolicy.documentDownload(url("https://agentbroker-jayk.onrender.com/companion/files/abc-123/download")))
precondition(!ClaraURLPolicy.documentDownload(url("https://evil.example/companion/files/abc/download")))
precondition(!ClaraURLPolicy.documentDownload(url("https://agentbroker-jayk.onrender.com/session/logout")))
precondition(ClaraURLPolicy.blobDownload(url("blob:https://agentbroker-jayk.onrender.com/id"), page: ClaraURLPolicy.home))
precondition(!ClaraURLPolicy.blobDownload(url("blob:https://evil.example/id"), page: ClaraURLPolicy.home))
precondition(!ClaraURLPolicy.blobDownload(url("blob:https://agentbroker-jayk.onrender.com/id"), page: url("https://evil.example")))
print("Native URL policy: trusted origin, port, credentials, download paths and blob scope passed.")
