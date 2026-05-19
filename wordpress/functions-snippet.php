<?php
/**
 * SEO Machine - Yoast REST API Support
 *
 * Add this code to your theme's functions.php file (or use a code snippets plugin).
 * This enables the SEO Machine tool to set Yoast SEO and Yoast SEO Premium meta
 * fields via REST API.
 *
 * Fields exposed:
 * - focus_keyphrase (Focus Keyphrase)
 * - seo_title (SEO Title)
 * - meta_description (Meta Description)
 */

add_action('rest_api_init', function() {
    // Only proceed if Yoast SEO is active
    if (!defined('WPSEO_VERSION') && !defined('WPSEO_PREMIUM_FILE') && !class_exists('WPSEO_Options')) {
        return;
    }

    $post_types = get_post_types(['show_in_rest' => true], 'names');
    $post_types = array_values(array_unique(array_merge(['post', 'page'], $post_types)));

    register_rest_field($post_types, 'yoast_seo', [
        'get_callback' => function($post) {
            return [
                'focus_keyphrase' => get_post_meta($post['id'], '_yoast_wpseo_focuskw', true),
                'seo_title' => get_post_meta($post['id'], '_yoast_wpseo_title', true),
                'meta_description' => get_post_meta($post['id'], '_yoast_wpseo_metadesc', true),
                'canonical' => get_post_meta($post['id'], '_yoast_wpseo_canonical', true),
            ];
        },
        'update_callback' => function($value, $post) {
            if (!current_user_can('edit_post', $post->ID)) {
                return new WP_Error('rest_forbidden', 'Permission denied.', ['status' => 403]);
            }

            if (isset($value['focus_keyphrase'])) {
                update_post_meta($post->ID, '_yoast_wpseo_focuskw', sanitize_text_field($value['focus_keyphrase']));
            }
            if (isset($value['seo_title'])) {
                update_post_meta($post->ID, '_yoast_wpseo_title', sanitize_text_field($value['seo_title']));
            }
            if (isset($value['meta_description'])) {
                update_post_meta($post->ID, '_yoast_wpseo_metadesc', sanitize_text_field($value['meta_description']));
            }
            if (isset($value['canonical'])) {
                update_post_meta($post->ID, '_yoast_wpseo_canonical', esc_url_raw($value['canonical']));
            }

            return true;
        },
        'schema' => [
            'type' => 'object',
            'properties' => [
                'focus_keyphrase' => ['type' => 'string', 'description' => 'Yoast Focus Keyphrase'],
                'seo_title' => ['type' => 'string', 'description' => 'Yoast SEO Title'],
                'meta_description' => ['type' => 'string', 'description' => 'Yoast Meta Description'],
                'canonical' => ['type' => 'string', 'description' => 'Yoast Canonical URL'],
            ],
        ],
    ]);

    register_rest_route('seo-machine/v1', '/yoast/status', [
        'methods' => 'GET',
        'permission_callback' => function() {
            return current_user_can('edit_posts');
        },
        'callback' => function() use ($post_types) {
            return [
                'yoast_active' => defined('WPSEO_VERSION') || defined('WPSEO_PREMIUM_FILE') || class_exists('WPSEO_Options'),
                'yoast_version' => defined('WPSEO_VERSION') ? WPSEO_VERSION : null,
                'yoast_premium_active' => defined('WPSEO_PREMIUM_FILE'),
                'post_types' => $post_types,
                'rest_field' => 'yoast_seo',
                'indexnow_key_route' => true,
                'indexnow_key_location' => home_url('/indexnow-key.txt'),
            ];
        },
    ]);
});

add_action('rest_api_init', function() {
    register_rest_route('seo-machine/v1', '/indexnow/key', [
        'methods' => 'POST',
        'permission_callback' => function() {
            return current_user_can('manage_options');
        },
        'callback' => function(WP_REST_Request $request) {
            $key = sanitize_text_field($request->get_param('key'));
            if (!$key || !preg_match('/^[A-Za-z0-9_-]{8,128}$/', $key)) {
                return new WP_Error('invalid_indexnow_key', 'Invalid IndexNow key.', ['status' => 400]);
            }
            update_option('seo_machine_indexnow_key', $key, false);
            flush_rewrite_rules(false);
            return [
                'ok' => true,
                'key_location' => home_url('/indexnow-key.txt'),
            ];
        },
    ]);
});

add_action('init', function() {
    add_rewrite_rule('^indexnow-key\.txt$', 'index.php?seo_machine_indexnow_key=1', 'top');
});

add_filter('query_vars', function($vars) {
    $vars[] = 'seo_machine_indexnow_key';
    return $vars;
});

add_action('template_redirect', function() {
    if (!get_query_var('seo_machine_indexnow_key')) {
        return;
    }
    $key = get_option('seo_machine_indexnow_key', '');
    if (!$key) {
        status_header(404);
        exit;
    }
    header('Content-Type: text/plain; charset=utf-8');
    echo esc_html($key);
    exit;
});
