# WordPress Site Review

Checked against `https://blog.meetlyra.app` through the WordPress REST API.

## Current API Shape

- WordPress REST works through query routes: `/?rest_route=/wp/v2/...`.
- Pretty `/wp-json/wp/v2/...` routes currently return HTML on this host.
- The content machine supports both styles and falls back to query routes automatically.

## Required Before Autonomous Publishing

- Install `wordpress/seo-machine-yoast-rest.php` as:
  `wp-content/mu-plugins/seo-machine-yoast-rest.php`
- If you prefer wp-admin upload, use `wordpress/seo-machine-yoast-rest.zip`
  and activate the plugin after upload.
- Run:
  `python -m content_machine doctor --live`
- The WordPress check should report `yoast_bridge.ok: true`.

Without that bridge, posts can be created through the API, but Yoast title,
description, and focus keyphrase will not be reliably written.

I verified this with a temporary draft probe: WordPress accepted the draft, but
direct `_yoast_wpseo_*` values sent through the normal `meta` field were ignored
and the response still lacked `yoast_seo`. The temporary draft was deleted.

## Yoast Premium Connection

The site currently has both `wordpress-seo/wp-seo` and
`wordpress-seo-premium/wp-seo-premium` active, version `27.3`.

The bridge does not bypass Yoast Premium. It writes the same canonical Yoast post
meta fields that the plugin UI saves:

- `_yoast_wpseo_focuskw`
- `_yoast_wpseo_title`
- `_yoast_wpseo_metadesc`
- `_yoast_wpseo_canonical`

After installation, the bridge also exposes:
`/?rest_route=/seo-machine/v1/yoast/status`

## Live Cleanup Items

- Change permalink settings from plain IDs to a post-name structure so posts use
  clean URLs instead of `?p=11`.
- Delete or unpublish the default `sample-page`.
- Replace the default `Uncategorized` category with intentional categories such
  as `SEO`, `AI Marketing`, and `Content Strategy`.
- Add tags to the existing post.
- Add a featured image and alt text to the existing post.

New content-machine publishes now create or reuse category and tag terms before
writing posts, so future posts should not default to `Uncategorized` once the
worker is allowed to publish.
