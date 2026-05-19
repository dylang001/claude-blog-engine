# Ultimate SEO Content Machine

This repo now includes a standalone autonomous worker that combines:

- Blog Engine keyword/topic pipeline patterns.
- SEOmachine WordPress + Yoast REST publishing patterns.
- Claude SEO audit/technical/schema/GSC/GA4/PageSpeed reference assets.
- A custom scheduler, SQLite state store, quality gate, WordPress client, and Banana Claude/Gemini image generator.

## Safe WordPress Setup

Use the official/free Yoast SEO plugin. Do not use nulled premium plugins.

Install one REST bridge option from `wordpress/`:

1. Preferred: upload `wordpress/seo-machine-yoast-rest.php` to `wp-content/mu-plugins/seo-machine-yoast-rest.php`.
2. Alternative: copy `wordpress/functions-snippet.php` into a trusted code snippets plugin.

Create a WordPress Application Password for a user that can edit posts.

## Configure

```bash
cp .env.example .env
cp config/site.example.yaml config/site.yaml
```

Fill in:

- `ANTHROPIC_API_KEY`
- `DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD`, or `DATAFORSEO_AUTH_BASE64`
  / `DATAFORSEO_BASE_64` containing `login:password` encoded as Base64
- `WP_BASE_URL`
- `WP_USERNAME`
- `WP_APP_PASSWORD`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GA4_PROPERTY_ID`
- `GSC_SITE_URL`
- Optional: `GEMINI_API_KEY` or `GOOGLE_AI_API_KEY`
- Optional but recommended: `INDEXNOW_KEY`, `INDEXNOW_KEY_LOCATION`, and
  `INDEXNOW_ENGINES` for immediate Bing/Yandex/Seznam/IndexNow
  notifications after publishing.

The worker never sends WordPress credentials to the LLM. Credentials stay in env vars and are only used by the narrow WordPress REST client.

## Commands

```bash
python -m content_machine doctor
python -m content_machine doctor --live
python -m content_machine run --dry-run
python -m content_machine run --publish
python -m content_machine worker
```

Dry runs generate, audit, and persist run state without writing to WordPress.

Use `doctor --live` after editing `.env`; it validates provider auth and connectivity
without printing secret values.

## IndexNow

Install the updated WordPress bridge first, then configure and verify the key:

```bash
python -m content_machine indexnow --configure-wordpress
python -m content_machine indexnow --verify
```

You can also submit a URL manually:

```bash
python -m content_machine indexnow --url https://blog.example.com/example-post/
```

Published posts are submitted automatically after a successful WordPress publish
or update. IndexNow covers Bing, Yandex, Seznam, and the generic
IndexNow endpoint; normal blog articles are still discovered by Google through
Search Console, sitemap, internal links, and crawl signals.

Image generation follows the Banana Claude creative-director pattern vendored in
`vendor/banana-claude`: Gemini image models, 5-component prompts, 16:9 blog
headers, and no OpenAI/DALL-E dependency.

## Publishing Rules

- Score `>=85`: publish.
- Score `70-84`: save as WordPress draft.
- Score `<70`: block and persist the failed run for review.

The two default slots are `09:00` and `15:00` in `Africa/Johannesburg`.

## Render

`render.yaml` defines a background worker with a persistent disk at `/var/data`.

Set secrets in Render, then deploy. Keep `CONTENT_MACHINE_DRY_RUN=false` only after a successful local dry run and one test publish.
