<?php
/**
 * Arrivl AI Bot Analytics — Server-Side Pageview Tracking
 *
 * Paste this entire block into your theme's functions.php,
 * OR drop it as a file in wp-content/mu-plugins/arrivl-tracking.php
 * (mu-plugins always loads; no need to activate).
 *
 * Environment variable:
 *   ARRIVL_WEBSITE_KEY=ak_5ea0bffee92faafd430a5057caefd8243465ed8a
 *
 * Set it in your hosting panel (Kinsta / WP Engine / cPanel / etc.)
 * OR define it in wp-config.php ABOVE the "That's all" line:
 *   define('ARRIVL_WEBSITE_KEY', 'ak_5ea0bffee92faafd430a5057caefd8243465ed8a');
 *
 * WordPress reads server env vars via getenv(), so either approach works.
 */

add_action('template_redirect', function () {

    // ------------------------------------------------------------------ //
    // 1. Resolve the website key — env var first, then wp-config constant //
    // ------------------------------------------------------------------ //
    $website_key = getenv('ARRIVL_WEBSITE_KEY');
    if (empty($website_key) && defined('ARRIVL_WEBSITE_KEY')) {
        $website_key = ARRIVL_WEBSITE_KEY;
    }
    if (empty($website_key)) {
        return; // Key not configured — fail silently
    }

    // ------------------------------------------------------------------ //
    // 2. Build the full request URL                                        //
    // ------------------------------------------------------------------ //
    $scheme   = is_ssl() ? 'https' : 'http';
    $host     = isset($_SERVER['HTTP_HOST']) ? $_SERVER['HTTP_HOST'] : '';
    $request_uri = isset($_SERVER['REQUEST_URI']) ? $_SERVER['REQUEST_URI'] : '/';
    $full_url = $scheme . '://' . $host . $request_uri;

    // ------------------------------------------------------------------ //
    // 3. ALLOWLIST — always track these even if they look like assets      //
    //    (AI crawlers read these to discover & classify the site)          //
    // ------------------------------------------------------------------ //
    $path = strtok($request_uri, '?'); // strip query string for matching

    $always_track = [
        '/robots.txt',
        '/llms.txt',
        '/llms-full.txt',
        '/sitemap.xml',
        '/ai.txt',
    ];

    $is_allowlisted = in_array($path, $always_track, true)
        // /sitemap-*.xml  (e.g. /sitemap-posts-1.xml)
        || (bool) preg_match('#^/sitemap-.+\.xml$#i', $path)
        // /.well-known/*
        || (bool) preg_match('#^/\.well-known/#', $path);

    // ------------------------------------------------------------------ //
    // 4. SKIP rules — skip static assets and WordPress internals           //
    //    The allowlist above always overrides these.                        //
    // ------------------------------------------------------------------ //
    if (! $is_allowlisted) {
        // WordPress REST API or any /wp-json/* path
        if (preg_match('#^/wp-json/#i', $path)) {
            return;
        }

        // WordPress admin, login, cron, XML-RPC
        if (preg_match('#^/wp-(admin|login\.php|cron\.php|xmlrpc\.php)#i', $path)) {
            return;
        }

        // wp-content static files (uploads, plugins, themes assets)
        if (preg_match('#^/wp-content/#i', $path)) {
            return;
        }

        // favicon / manifest
        if (preg_match('#^/(favicon\.ico|manifest\.webmanifest)$#i', $path)) {
            return;
        }

        // Static-asset extensions
        $static_ext = '/\.(png|jpe?g|svg|gif|webp|ico|css|js|mjs|map|woff2?|ttf|otf|eot|txt|xml|json)$/i';
        if (preg_match($static_ext, $path)) {
            return;
        }
    }

    // ------------------------------------------------------------------ //
    // 5. Collect tracking parameters                                       //
    // ------------------------------------------------------------------ //
    $user_agent = isset($_SERVER['HTTP_USER_AGENT']) ? $_SERVER['HTTP_USER_AGENT'] : '';
    $referer    = isset($_SERVER['HTTP_REFERER'])    ? $_SERVER['HTTP_REFERER']    : '';

    // x-forwarded-for: take the first IP and trim whitespace
    $xff = isset($_SERVER['HTTP_X_FORWARDED_FOR']) ? $_SERVER['HTTP_X_FORWARDED_FOR'] : '';
    $ip  = trim(explode(',', $xff)[0]);

    // ------------------------------------------------------------------ //
    // 6. Fire the non-blocking GET — fire-and-forget                      //
    // ------------------------------------------------------------------ //
    $endpoint = 'https://arrivl.ai/api/v1/intake/pageview';
    $query    = http_build_query([
        'url'        => $full_url,
        'userAgent'  => $user_agent,
        'ref'        => $referer,
        'ip'         => $ip,
        'websiteKey' => $website_key,
    ]);

    wp_remote_get($endpoint . '?' . $query, [
        'blocking'  => false,   // fire-and-forget — does NOT wait for a response
        'timeout'   => 1,       // safeguard: WP uses this for the connect timeout
        'sslverify' => true,
        'user-agent' => 'WordPress/' . get_bloginfo('version') . '; ' . home_url(),
    ]);

    // No return value needed; WP discards the response when blocking=false
}, 1); // priority 1 — runs before any template output
