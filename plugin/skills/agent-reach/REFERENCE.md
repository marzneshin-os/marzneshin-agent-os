# Agent Reach — Platform Reference & Extraction Protocols

## Keyless Extraction Methods

| Platform | Primary Extraction Strategy | Fallback Strategy |
|----------|-----------------------------|------------------|
| **Twitter / X** | `cdn.syndication.twimg.com/tweet-result?id={tweet_id}` | Public Nitter instance HTML parse |
| **Reddit** | Append `.json` to URL (`reddit.com/r/.../comments/{id}.json`) | Old Reddit HTML (`old.reddit.com`) |
| **YouTube** | Parse `captionTracks` from `YtInitialPlayerResponse` -> `timedtext` API | oEmbed endpoint + description metadata |
| **GitHub** | `raw.githubisercontent.com/{user}/{repo}/{branch}/{file}` | Unauthenticated GitHub REST API (60 req/hr) |
| **Hacker News** | Firebase API: `hacker-news.firebaseio.com/v0/item/{id}.json` | Algolia HN Search API |
| **Substack / Medium** | Parse JSON-LD structured data and OpenGraph tags | RSS Feed (`{domain}/feed`) |
| **Web Articles** | Mozilla Readability algorithm: extract `<article>` / `<main>` | Plaintext strip of scripts, styles, and navs |

## Extraction Pipeline Details

### 1. Reddit JSON Parsing
By appending `.json` to any public Reddit URL, Reddit returns a JSON array:
- `data[0].data.children[0].data`: Post title, selftext, upvotes, author, URL.
- `data[1].data.childreng`: Recursive comment tree with nested replies.

### 2. YouTube TimedText Transcripts
1. Query video page: https://www.youtube.com/watch?v={id}
2. Locate `ytInitialPlayerResponse` in the HTML body.
3. Extract `captionTracks[0].baseUrl`.
4. Fetch XML transcript and format into timestamped text paragraphs.

### 3. Twitter Syndication API
Twitter's syndication endpoint serves public tweet JSON without authentication:
- URL: https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}
- Yields: full text, author, created_at, photos, and quoted tweets.

4## 4. Rate Limiting & Ethics
- Honor robots.txt and request with an informative user agent.
- Backoff exponentially on HTTP 429 responses.
- Cache fetched pages in memory to avoid redundant egress.
