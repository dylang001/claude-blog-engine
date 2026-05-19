<?php
/**
 * Plugin Name: SEO Machine - Yoast REST API Support
 * Description: Exposes Yoast SEO and Yoast SEO Premium meta fields via the WordPress REST API for the SEO Machine tool.
 * Version: 1.1
 * Author: SEO Machine
 *
 * Installation:
 * 1. Upload this file to: wp-content/mu-plugins/seo-machine-yoast-rest.php
 * 2. That's it - mu-plugins are automatically activated
 *
 * If the mu-plugins folder doesn't exist, create it.
 */

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

function seo_machine_yoast_rest_is_yoast_active() {
    return defined('WPSEO_VERSION') || defined('WPSEO_PREMIUM_FILE') || class_exists('WPSEO_Options');
}

function seo_machine_yoast_rest_post_types() {
    $post_types = get_post_types(['show_in_rest' => true], 'names');
    $post_types = array_values(array_unique(array_merge(['post', 'page'], $post_types)));

    return apply_filters('seo_machine_yoast_rest_post_types', $post_types);
}

function seo_machine_yoast_rest_meta_fields() {
    return [
        '_yoast_wpseo_focuskw' => [
            'description' => 'Yoast SEO Focus Keyphrase',
            'single' => true,
        ],
        '_yoast_wpseo_title' => [
            'description' => 'Yoast SEO Title',
            'single' => true,
        ],
        '_yoast_wpseo_metadesc' => [
            'description' => 'Yoast SEO Meta Description',
            'single' => true,
        ],
        '_yoast_wpseo_canonical' => [
            'description' => 'Yoast SEO Canonical URL',
            'single' => true,
        ],
        '_yoast_wpseo_linkdex' => [
            'description' => 'Yoast SEO Score',
            'single' => true,
        ],
        '_yoast_wpseo_content_score' => [
            'description' => 'Yoast Readability Score',
            'single' => true,
        ],
    ];
}

/**
 * Register Yoast SEO meta fields for REST API access
 */
add_action('init', function() {
    if (!seo_machine_yoast_rest_is_yoast_active()) {
        return;
    }

    foreach (seo_machine_yoast_rest_post_types() as $post_type) {
        foreach (seo_machine_yoast_rest_meta_fields() as $meta_key => $args) {
            register_post_meta($post_type, $meta_key, [
                'show_in_rest' => true,
                'single' => $args['single'],
                'type' => 'string',
                'description' => $args['description'],
                'auth_callback' => function() {
                    return current_user_can('edit_posts');
                },
            ]);
        }
    }
});

/**
 * Alternative: Add Yoast fields to REST response and handle updates
 * This provides a cleaner API interface
 */
add_action('rest_api_init', function() {
    if (!seo_machine_yoast_rest_is_yoast_active()) {
        return;
    }

    foreach (seo_machine_yoast_rest_post_types() as $post_type) {
        register_rest_field($post_type, 'yoast_seo', [
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
                    return new WP_Error('rest_forbidden', 'You do not have permission to edit this post.', ['status' => 403]);
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
                    'focus_keyphrase' => ['type' => 'string'],
                    'seo_title' => ['type' => 'string'],
                    'meta_description' => ['type' => 'string'],
                    'canonical' => ['type' => 'string'],
                ],
            ],
        ]);
    }

    register_rest_route('seo-machine/v1', '/yoast/status', [
        'methods' => 'GET',
        'permission_callback' => function() {
            return current_user_can('edit_posts');
        },
        'callback' => function() {
            return [
                'yoast_active' => seo_machine_yoast_rest_is_yoast_active(),
                'yoast_version' => defined('WPSEO_VERSION') ? WPSEO_VERSION : null,
                'yoast_premium_active' => defined('WPSEO_PREMIUM_FILE'),
                'post_types' => seo_machine_yoast_rest_post_types(),
                'meta_keys' => array_keys(seo_machine_yoast_rest_meta_fields()),
                'rest_field' => 'yoast_seo',
                'indexnow_key_route' => true,
                'indexnow_key_location' => home_url('/indexnow-key.txt'),
            ];
        },
    ]);

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
