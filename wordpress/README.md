# WordPress Integration Files

These files enable the SEO Machine tool to set Yoast SEO and Yoast SEO Premium
meta fields (Focus Keyphrase, SEO Title, Meta Description, Canonical URL) via
the REST API.

The bridge connects to Yoast through the standard `_yoast_wpseo_*` post meta
keys used by both the free and Premium plugins. On `blog.meetlyra.app`, the
active plugins are `wordpress-seo/wp-seo` and `wordpress-seo-premium/wp-seo-premium`.

**Choose ONE option** - either the mu-plugin OR the functions.php snippet. They do the same thing.

---

## Option A: MU-Plugin (Recommended)

**File:** `seo-machine-yoast-rest.php`

**Installation as an MU plugin:**
1. Upload to: `wp-content/mu-plugins/seo-machine-yoast-rest.php`
2. Create the `mu-plugins` folder if it doesn't exist
3. Done - mu-plugins auto-activate, no enabling required

**Installation through wp-admin plugin upload:**
1. Upload `seo-machine-yoast-rest.zip`
2. Activate `SEO Machine - Yoast REST API Support`

**Pros:**
- Won't be lost during theme updates
- Can't be accidentally deactivated
- Clean separation from theme code

---

## Option B: Functions.php Snippet

**File:** `functions-snippet.php`

**Installation:**
1. Copy the contents of this file
2. Paste at the end of your theme's `functions.php`
3. Or use a code snippets plugin (WPCode, Code Snippets, etc.)

**Pros:**
- No new files to manage
- Works with code snippet plugins

**Cons:**
- Lost if theme is changed/updated (unless using child theme)

---

## What This Code Does

Registers a custom REST API field called `yoast_seo` on REST-enabled post types
that allows reading and writing:

- `focus_keyphrase` → `_yoast_wpseo_focuskw`
- `seo_title` → `_yoast_wpseo_title`
- `meta_description` → `_yoast_wpseo_metadesc`
- `canonical` → `_yoast_wpseo_canonical`

It also registers a diagnostic route:

```text
GET /?rest_route=/seo-machine/v1/yoast/status
```

The content-machine doctor uses that route to confirm that Yoast and Yoast
Premium are visible to the bridge.

It also supports IndexNow verification for immediate post-publish indexing
notifications:

```text
POST /?rest_route=/seo-machine/v1/indexnow/key
GET /indexnow-key.txt
```

The content-machine sends the IndexNow key to WordPress through the REST route.
WordPress then serves the key at `/indexnow-key.txt`, which Bing, Yandex,
Naver, Seznam, and IndexNow use to verify URL ownership before accepting
submitted article URLs.

**API Usage:**
```json
POST /wp-json/wp/v2/posts/{id}
{
  "yoast_seo": {
    "focus_keyphrase": "your target keyword",
    "seo_title": "Your SEO Title | Brand",
    "meta_description": "Your meta description here.",
    "canonical": "https://example.com/your-post/"
  }
}
```

---

## Security

- Requires authentication (Application Password)
- User must have `edit_post` capability
- IndexNow key configuration requires `manage_options` capability
- All inputs are sanitized with `sanitize_text_field()`
