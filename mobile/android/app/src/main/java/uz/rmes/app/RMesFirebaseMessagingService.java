package uz.rmes.app;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

import androidx.core.app.NotificationCompat;

import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;

public class RMesFirebaseMessagingService extends FirebaseMessagingService {
    public static final String PREFS = "rmes_native";
    public static final String PUSH_TOKEN = "push_token";

    @Override public void onNewToken(String token) {
        getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(PUSH_TOKEN, token).apply();
        sendBroadcast(new Intent("uz.rmes.app.PUSH_TOKEN_UPDATED").setPackage(getPackageName()).putExtra("token", token));
    }

    @Override public void onMessageReceived(RemoteMessage message) {
        String title = message.getNotification()!=null ? message.getNotification().getTitle() : message.getData().get("title");
        String body = message.getNotification()!=null ? message.getNotification().getBody() : message.getData().get("body");
        String url = message.getData().get("url");
        if (title == null || title.isEmpty()) title = "R-Mes";
        if (body == null || body.isEmpty()) body = "Новое сообщение";
        show(title, body, url);
    }

    private void show(String title, String body, String url) {
        NotificationManager manager=(NotificationManager)getSystemService(Context.NOTIFICATION_SERVICE);
        String channel="rmes_messages";
        if(Build.VERSION.SDK_INT>=26) manager.createNotificationChannel(new NotificationChannel(channel,"Сообщения R-Mes",NotificationManager.IMPORTANCE_HIGH));
        Intent launch=new Intent(this,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP|Intent.FLAG_ACTIVITY_SINGLE_TOP);
        if(url!=null) launch.putExtra("rmes_url",url);
        PendingIntent pending=PendingIntent.getActivity(this,(int)System.currentTimeMillis(),launch,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        NotificationCompat.Builder b=new NotificationCompat.Builder(this,channel).setSmallIcon(R.drawable.ic_stat_rmes).setContentTitle(title).setContentText(body).setAutoCancel(true).setPriority(NotificationCompat.PRIORITY_HIGH).setContentIntent(pending);
        manager.notify((int)(System.currentTimeMillis()%Integer.MAX_VALUE),b.build());
    }
}
