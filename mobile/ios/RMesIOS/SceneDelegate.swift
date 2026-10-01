import UIKit
import WebKit

final class SceneDelegate: UIResponder, UIWindowSceneDelegate, WKNavigationDelegate, WKUIDelegate {
    var window: UIWindow?
    private var webView: WKWebView!
    private var splashView: UIView?

    func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options connectionOptions: UIScene.ConnectionOptions) {
        guard let ws = scene as? UIWindowScene else { return }
        let cfg = WKWebViewConfiguration()
        cfg.allowsInlineMediaPlayback = true
        cfg.mediaTypesRequiringUserActionForPlayback = []
        cfg.websiteDataStore = .default()
        webView = WKWebView(frame: .zero, configuration: cfg)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.customUserAgent = AppConfig.userAgent
        let vc = UIViewController(); vc.view = webView
        let splash=makeSplash(); splash.frame=webView.bounds; splash.autoresizingMask=[.flexibleWidth,.flexibleHeight]; webView.addSubview(splash); splashView=splash
        let w = UIWindow(windowScene: ws); w.rootViewController = vc; w.makeKeyAndVisible(); window = w
        NotificationCenter.default.addObserver(self,selector:#selector(pushTokenUpdated(_:)),name:.rmesPushTokenUpdated,object:nil)
        NotificationCenter.default.addObserver(self,selector:#selector(openPushURL(_:)),name:.rmesOpenURL,object:nil)
        if let context=connectionOptions.urlContexts.first { openRMesURL(context.url) }
        else if let pending=UserDefaults.standard.string(forKey:"rmes_pending_url") { UserDefaults.standard.removeObject(forKey:"rmes_pending_url"); openRMesURL(URL(string:pending)) }
        else { loadStart() }
    }

    deinit { NotificationCenter.default.removeObserver(self) }

    private func makeSplash() -> UIView {
        let v=UIView(); v.backgroundColor=UIColor(red:14/255,green:22/255,blue:33/255,alpha:1)
        let stack=UIStackView(); stack.axis=.vertical; stack.alignment=.center; stack.spacing=8; stack.translatesAutoresizingMaskIntoConstraints=false
        let icon=UIView(); icon.backgroundColor=UIColor(red:42/255,green:171/255,blue:238/255,alpha:1); icon.layer.cornerRadius=26; icon.widthAnchor.constraint(equalToConstant:92).isActive=true; icon.heightAnchor.constraint(equalToConstant:92).isActive=true
        let mark=UILabel(); mark.text="R"; mark.textColor=.white; mark.font=.systemFont(ofSize:48,weight:.heavy); mark.translatesAutoresizingMaskIntoConstraints=false; icon.addSubview(mark); NSLayoutConstraint.activate([mark.centerXAnchor.constraint(equalTo:icon.centerXAnchor),mark.centerYAnchor.constraint(equalTo:icon.centerYAnchor)])
        let title=UILabel(); title.text="R-Messanger"; title.textColor=.white; title.font=.systemFont(ofSize:28,weight:.bold)
        let sub=UILabel(); sub.text="быстро · приватно · красиво"; sub.textColor=UIColor(red:142/255,green:166/255,blue:184/255,alpha:1); sub.font=.systemFont(ofSize:12,weight:.medium)
        let spinner=UIActivityIndicatorView(style:.medium); spinner.color=UIColor(red:42/255,green:171/255,blue:238/255,alpha:1); spinner.startAnimating()
        stack.addArrangedSubview(icon); stack.addArrangedSubview(title); stack.addArrangedSubview(sub); stack.addArrangedSubview(spinner); stack.setCustomSpacing(20,after:sub)
        v.addSubview(stack); NSLayoutConstraint.activate([stack.centerXAnchor.constraint(equalTo:v.centerXAnchor),stack.centerYAnchor.constraint(equalTo:v.centerYAnchor)])
        return v
    }

    private func loadStart() {
        let url = AppConfig.serverURL.appendingPathComponent("auth/app-lock/client-start/")
        var req = URLRequest(url: url); req.setValue("ios", forHTTPHeaderField: "X-R-Mes-Client"); webView.load(req)
    }

    @objc private func pushTokenUpdated(_ note:Notification){ emitPushToken(note.object as? String) }
    @objc private func openPushURL(_ note:Notification){ if let raw=note.object as? String { openRMesURL(URL(string:raw)) } }

    private func emitPushToken(_ supplied:String?=nil) {
        guard let token=supplied ?? UserDefaults.standard.string(forKey:"rmes_apns_token"), !token.isEmpty else { return }
        let safe=token.replacingOccurrences(of:"'",with:"\\'")
        webView.evaluateJavaScript("window.dispatchEvent(new CustomEvent('rmes:native-push-token',{detail:{provider:'apns',token:'\(safe)'}}))")
    }

    private func openRMesURL(_ url:URL?) {
        guard let url=url else { loadStart(); return }
        if url.scheme=="rmes", url.host=="chat" {
            let chat=url.path.trimmingCharacters(in:CharacterSet(charactersIn:"/"))
            if !chat.isEmpty {
                var target=AppConfig.serverURL.appendingPathComponent("c/\(chat)/")
                if let parts=URLComponents(url:url,resolvingAgainstBaseURL:false), let message=parts.queryItems?.first(where:{$0.name=="message"})?.value {
                    var dst=URLComponents(url:target,resolvingAgainstBaseURL:false)!; dst.queryItems=[URLQueryItem(name:"jump",value:message)]; dst.fragment="msg-\(message)"; if let u=dst.url { target=u }
                }
                webView.load(URLRequest(url:target)); return
            }
        }
        loadStart()
    }

    func scene(_ scene: UIScene, openURLContexts URLContexts: Set<UIOpenURLContext>) { if let url=URLContexts.first?.url { openRMesURL(url) } }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        emitPushToken()
        if let splash=splashView { UIView.animate(withDuration:0.28,animations:{splash.alpha=0}) {_ in splash.removeFromSuperview();self.splashView=nil} }
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        let html = """<html><meta name='viewport' content='width=device-width'><body style='background:#0e1621;color:white;font-family:-apple-system;padding:40px'><h2>R-Messanger недоступен</h2><p>Проверьте интернет. Последние открытые данные остаются в памяти приложения.</p><button onclick='location.reload()' style='padding:12px 18px;border:0;border-radius:12px;background:#2AABEE;color:white'>Повторить</button></body></html>"""
        webView.loadHTMLString(html, baseURL: nil)
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else { decisionHandler(.cancel); return }
        if url.scheme == "rmes" { openRMesURL(url); decisionHandler(.cancel); return }
        if url.host == AppConfig.serverURL.host { decisionHandler(.allow); return }
        if ["http","https","mailto","tel"].contains(url.scheme ?? "") { UIApplication.shared.open(url); decisionHandler(.cancel); return }
        decisionHandler(.allow)
    }
}
