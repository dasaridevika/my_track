export default {
  async fetch(request, env) {
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type"
    };
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: corsHeaders
      });
    }
    try {
      let text = "";
      let sourceUrl = "";
      let title = "";
      let analysisType = "summary";

      if (request.method === "GET") {
        text = "Cloudflare Workers AI helps developers build AI applications on the edge with low latency.";
        sourceUrl = "browser-test";
        title = "Sample Input";
      } else if (request.method === "POST") {
        const body = await request.json();
        if (!body.text || typeof body.text !== "string" || !body.text.trim()) {
          return Response.json(
            {
              success: false,
              error: "Missing or invalid 'text' field in request body."
            },
            {
              status: 400,
              headers: corsHeaders
            }
          );
        }
        text = body.text.trim();
        sourceUrl = body.url || "";
        title = body.title || "";
        analysisType = body.analysis_type || "summary";
      } else {
        return Response.json(
          {
            success: false,
            error: "Method not allowed"
          },
          {
            status: 405,
            headers: corsHeaders
          }
        );
      }
      const prompt = `
You are an expert AI analyst.

Analyze the following extracted webpage content.

Return ONLY a valid JSON object.
Do NOT include markdown.
Do NOT wrap the response inside \`\`\`json.
Do NOT add explanations.

Return exactly this schema:
{
  "summary": "",
  "topics": [],
  "keywords": [],
  "sentiment": "",
  "important_points": [],
  "action_items": []
}
Analysis Type: ${analysisType}
Source URL: ${sourceUrl}
Title: ${title}
Content:
${text}
`;

      const start = Date.now();

      const result = await env.AI.run("@cf/meta/llama-4-scout-17b-16e-instruct", {
        messages: [
          {
            role: "system",
            content: "You are a professional webpage analysis assistant. Always return valid JSON only."
          },
          {
            role: "user",
            content: prompt
          }
        ],
        max_tokens: 700,
        temperature: 0.2
      });

      const latencyMs = Date.now() - start;

      let output = result.response ?? result;

if (typeof output === "object") {
  output = JSON.stringify(output);
} else {
  output = String(output || "").trim();
}

output = output
  .replace(/```json/gi, "")
  .replace(/```/g, "")
  .trim();

      let parsed;

      try {
        parsed = JSON.parse(output);
      } catch {
        return Response.json(
          {
            success: false,
            error: "Model returned invalid JSON.",
            raw_response: result.response || null,
            latency_ms: latencyMs
          },
          {
            status: 500,
            headers: corsHeaders
          }
        );
      }

      return Response.json(
        {
          success: true,
          model: "@cf/meta/llama-4-scout-17b-16e-instruct",
          analysis_type: analysisType,
          source_url: sourceUrl,
          title,
          latency_ms: latencyMs,
          result: parsed,
          usage: result.usage || null
        },
        {
          headers: corsHeaders
        }
      );
    } catch (err) {
      return Response.json(
        {
          success: false,
          error: err.message || "Internal server error"
        },
        {
          status: 500,
          headers: corsHeaders
        }
      );
    }
  }
};
