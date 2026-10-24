# Claude API — Reference & Multi-Language Implementation

## 1. TypeScript / Node.js
```typescript
import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
const response = await client.messages.create({
  model: "claude-3-7-sonnet-20250219",
  max_tokens: 1024,
  system: [
    {
      type: "text",
      text: "You are an expert systems engineer.",
      cache_control: { type: "ephemeral" }
    }
  ],
  messages: [{ role: "user", content: "Analyze memory leak patterns." }]
});
console.log(response.content[0].text);
```

## 2. Python
```python
import anthropic

client = anthropic.Anthropic()
message = client.messages.create(
    model="claude-3-7-sonnet-20250219",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": "You are a concise data architect.",
            "cache_control": {"type": "ephemeral"}
        }
    ],
    messages=[{"role": "user", "content": "Explain hybrid BM25 + vector search."}]
)
print(message.content[0].text)
```

## 3. Go
``go
package main

import (
	"context"
	"fmt"
	"os"
	"github.com/anthropics/anthropic-sdk-go"
)

func main() {
	client := anthropic.NewClient(anthropic.WithAPIKey(os.Getenv("ANTHROPIC_API_KEY")))
	resp, err := client.Messages.New(context.Background(), anthropic.MessageNewParams{
		Model:     anthropic.F(anthropic.ModelClaude3_7SonnetLatest),
		MaxTokens: anthropic.F(int64(1024)),
		Messages: anthropic.F([]anthropic.MessageParam{
			anthropic.NewUserMessage(anthropic.NewTextBlock("Verify cluster state.")),
		}),
	})
	if err != nil {
		panic(err)
	}
	fmt.Println(resp.Content[0].Text)
}
```

## 4. cuRL

```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-3-7-sonnet-20250219",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Ping"}]
  }'
```
