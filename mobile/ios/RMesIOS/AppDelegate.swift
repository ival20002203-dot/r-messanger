import UIKit
import UserNotifications

@main
final class AppDelegate: UIResponder, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        let center=UNUserNotificationCenter.current()
        center.delegate=self
        center.requestAuthorization(options:[.alert,.badge,.sound]) { granted,_ in
            if granted { DispatchQueue.main.async { application.registerForRemoteNotifications() } }
        }
        return true
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let token=deviceToken.map { String(format:"%02.2hhx",$0) }.joined()
        UserDefaults.standard.set(token,forKey:"rmes_apns_token")
        NotificationCenter.default.post(name:.rmesPushTokenUpdated,object:token)
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        print("R-Mes APNs registration failed: \(error)")
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification, withCompletionHandler completionHandler:@escaping (UNNotificationPresentationOptions)->Void) {
        completionHandler([.banner,.sound,.badge])
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse, withCompletionHandler completionHandler:@escaping ()->Void) {
        if let rmes=response.notification.request.content.userInfo["rmes"] as? [String:Any], let url=rmes["url"] as? String {
            UserDefaults.standard.set(url,forKey:"rmes_pending_url")
            NotificationCenter.default.post(name:.rmesOpenURL,object:url)
        }
        completionHandler()
    }
}

extension Notification.Name {
    static let rmesPushTokenUpdated=Notification.Name("RMesPushTokenUpdated")
    static let rmesOpenURL=Notification.Name("RMesOpenURL")
}
