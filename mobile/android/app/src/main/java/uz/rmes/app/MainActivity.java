package uz.rmes.app;

import android.Manifest;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.BroadcastReceiver;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.Settings;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.ProgressBar;
import android.view.Gravity;
import android.graphics.Color;

import com.google.firebase.messaging.FirebaseMessaging;

import java.util.HashMap;
import java.util.Map;

public class MainActivity extends Activity {
    private static final int FILE_CHOOSER = 1201;
    private static final int MEDIA_PERMISSIONS = 1202;
    private WebView webView;
    private View splashView;
    private ValueCallback<Uri[]> fileCallback;
    private String serverUrl;
    private long pendingApkDownload = -1L;
    private boolean receiverRegistered = false;

    private final BroadcastReceiver downloadReceiver = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            if (!DownloadManager.ACTION_DOWNLOAD_COMPLETE.equals(intent.getAction())) return;
            long id = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1L);
            if (id != pendingApkDownload) return;
            pendingApkDownload = -1L;
            DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
            Uri uri = dm.getUriForDownloadedFile(id);
            if (uri == null) {
                Toast.makeText(MainActivity.this, "Не удалось открыть обновление", Toast.LENGTH_LONG).show();
                return;
            }
            try {
                Intent install = new Intent(Intent.ACTION_VIEW);
                install.setDataAndType(uri, "application/vnd.android.package-archive");
                install.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(install);
            } catch (Exception e) {
                Toast.makeText(MainActivity.this, "Откройте загруженный APK из уведомления", Toast.LENGTH_LONG).show();
            }
        }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        serverUrl = getString(R.string.server_url).replaceAll("/+$", "");
        FrameLayout root=new FrameLayout(this);
        webView = new WebView(this);
        root.addView(webView,new FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT,FrameLayout.LayoutParams.MATCH_PARENT));
        splashView=createSplashView();
        root.addView(splashView,new FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT,FrameLayout.LayoutParams.MATCH_PARENT));
        setContentView(root);
        configureWebView();
        registerDownloadReceiver();
        requestMediaPermissions();
        try {
            FirebaseMessaging.getInstance().getToken().addOnSuccessListener(token -> {
                if (token != null && !token.isEmpty()) getSharedPreferences(RMesFirebaseMessagingService.PREFS, MODE_PRIVATE).edit().putString(RMesFirebaseMessagingService.PUSH_TOKEN, token).apply();
                emitPushToken();
            });
        } catch (Exception ignored) {
            // Firebase is optional in local/sideload builds without google-services.json.
        }
        if (state == null) { if (!openIntentUrl(getIntent())) loadStart(); } else webView.restoreState(state);
    }

    private View createSplashView() {
        LinearLayout box=new LinearLayout(this); box.setOrientation(LinearLayout.VERTICAL); box.setGravity(Gravity.CENTER); box.setBackgroundColor(Color.rgb(14,22,33));
        ImageView logo=new ImageView(this); logo.setImageResource(R.drawable.rmes_icon); int size=(int)(96*getResources().getDisplayMetrics().density); box.addView(logo,new LinearLayout.LayoutParams(size,size));
        TextView title=new TextView(this); title.setText("R-Messanger"); title.setTextColor(Color.WHITE); title.setTextSize(27); title.setGravity(Gravity.CENTER); LinearLayout.LayoutParams tp=new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT,LinearLayout.LayoutParams.WRAP_CONTENT); tp.topMargin=18; box.addView(title,tp);
        TextView sub=new TextView(this); sub.setText("быстро · приватно · красиво"); sub.setTextColor(Color.rgb(142,166,184)); sub.setTextSize(12); LinearLayout.LayoutParams sp=new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT,LinearLayout.LayoutParams.WRAP_CONTENT); sp.topMargin=6; box.addView(sub,sp);
        ProgressBar bar=new ProgressBar(this); LinearLayout.LayoutParams bp=new LinearLayout.LayoutParams((int)(34*getResources().getDisplayMetrics().density),(int)(34*getResources().getDisplayMetrics().density)); bp.topMargin=22; box.addView(bar,bp);
        return box;
    }

    private void configureWebView() {
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setUserAgentString(s.getUserAgentString() + " RMesAndroid/15.1.2");

        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, false);

        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (uri.toString().startsWith(serverUrl)) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); } catch (ActivityNotFoundException ignored) {}
                return true;
            }
            @Override public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                CookieManager.getInstance().flush();
                emitPushToken();
                if (splashView != null && splashView.getVisibility() == View.VISIBLE) splashView.animate().alpha(0f).setDuration(260).withEndAction(() -> splashView.setVisibility(View.GONE)).start();
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override public void onPermissionRequest(PermissionRequest request) {
                runOnUiThread(() -> request.grant(request.getResources()));
            }
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                try {
                    Intent intent = params.createIntent();
                    intent.addCategory(Intent.CATEGORY_OPENABLE);
                    startActivityForResult(intent, FILE_CHOOSER);
                    return true;
                } catch (Exception e) {
                    fileCallback = null;
                    Toast.makeText(MainActivity.this, "Не удалось открыть выбор файла", Toast.LENGTH_SHORT).show();
                    return false;
                }
            }
        });

        webView.setDownloadListener((url, userAgent, contentDisposition, mimeType, contentLength) -> {
            try {
                DownloadManager.Request req = new DownloadManager.Request(Uri.parse(url));
                String cookies = CookieManager.getInstance().getCookie(url);
                if (cookies != null) req.addRequestHeader("Cookie", cookies);
                req.addRequestHeader("User-Agent", userAgent + " RMesAndroid/15.1.2");
                req.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                String filename = android.webkit.URLUtil.guessFileName(url, contentDisposition, mimeType);
                req.setTitle(filename);
                req.setDestinationInExternalFilesDir(this, Environment.DIRECTORY_DOWNLOADS, filename);
                DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
                long downloadId = dm.enqueue(req);
                if (filename.toLowerCase().endsWith(".apk")) pendingApkDownload = downloadId;
                Toast.makeText(this, filename.toLowerCase().endsWith(".apk") ? "Обновление загружается…" : "Файл загружается", Toast.LENGTH_LONG).show();
                if (filename.endsWith(".apk") && android.os.Build.VERSION.SDK_INT >= 26 && !getPackageManager().canRequestPackageInstalls()) {
                    Intent settingsIntent = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + getPackageName()));
                    startActivity(settingsIntent);
                }
            } catch (Exception e) {
                Toast.makeText(this, "Ошибка загрузки: " + e.getMessage(), Toast.LENGTH_LONG).show();
            }
        });
    }


    private void emitPushToken() {
        if (webView == null) return;
        String token=getSharedPreferences(RMesFirebaseMessagingService.PREFS, MODE_PRIVATE).getString(RMesFirebaseMessagingService.PUSH_TOKEN, "");
        if (token == null || token.isEmpty()) return;
        String safe=token.replace("\\","\\\\").replace("'","\\'").replace("\n","");
        webView.evaluateJavascript("window.dispatchEvent(new CustomEvent('rmes:native-push-token',{detail:{provider:'fcm',token:'"+safe+"'}}))", null);
    }

    private boolean openIntentUrl(Intent intent) {
        if (intent == null) return false;
        String raw=intent.getStringExtra("rmes_url");
        Uri uri=raw!=null?Uri.parse(raw):intent.getData();
        if (uri == null || !"rmes".equalsIgnoreCase(uri.getScheme())) return false;
        if ("chat".equalsIgnoreCase(uri.getHost())) {
            String path=uri.getPath(); if (path!=null && path.startsWith("/")) path=path.substring(1);
            if (path!=null && !path.isEmpty()) {
                String message=uri.getQueryParameter("message");
                String target=serverUrl+"/c/"+path+"/"+(message!=null?"?jump="+Uri.encode(message)+"#msg-"+Uri.encode(message):"");
                webView.loadUrl(target); return true;
            }
        }
        loadStart(); return true;
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent); setIntent(intent); openIntentUrl(intent);
    }

    private void registerDownloadReceiver() {
        if (receiverRegistered) return;
        IntentFilter filter = new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE);
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(downloadReceiver, filter, Context.RECEIVER_EXPORTED);
        else registerReceiver(downloadReceiver, filter);
        receiverRegistered = true;
    }

    private void loadStart() {
        Map<String,String> headers = new HashMap<>();
        headers.put("X-R-Mes-Client", "android");
        webView.loadUrl(serverUrl + "/auth/app-lock/client-start/", headers);
    }

    private void requestMediaPermissions() {
        if (android.os.Build.VERSION.SDK_INT >= 23) {
            java.util.ArrayList<String> need = new java.util.ArrayList<>();
            if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) need.add(Manifest.permission.CAMERA);
            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) need.add(Manifest.permission.RECORD_AUDIO);
            if (android.os.Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) need.add(Manifest.permission.POST_NOTIFICATIONS);
            if (!need.isEmpty()) requestPermissions(need.toArray(new String[0]), MEDIA_PERMISSIONS);
        }
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_CHOOSER && fileCallback != null) {
            Uri[] result = WebChromeClient.FileChooserParams.parseResult(resultCode, data);
            fileCallback.onReceiveValue(result);
            fileCallback = null;
        }
    }

    @Override protected void onSaveInstanceState(Bundle outState) {
        webView.saveState(outState);
        super.onSaveInstanceState(outState);
    }

    @Override public void onBackPressed() {
        if (webView.canGoBack()) webView.goBack(); else super.onBackPressed();
    }

    @Override protected void onResume() {
        super.onResume();
        webView.onResume();
        webView.evaluateJavascript("window.dispatchEvent(new Event('focus'))", null);
    }

    @Override protected void onPause() {
        webView.evaluateJavascript("window.dispatchEvent(new Event('blur'))", null);
        webView.onPause();
        CookieManager.getInstance().flush();
        super.onPause();
    }

    @Override protected void onDestroy() {
        if (receiverRegistered) {
            try { unregisterReceiver(downloadReceiver); } catch (Exception ignored) {}
            receiverRegistered = false;
        }
        if (webView != null) {
            webView.loadUrl("about:blank");
            webView.destroy();
        }
        super.onDestroy();
    }
}
