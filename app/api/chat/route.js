export async function POST(request) {
    var body = await request.json();
    var message = body.message;
    var currentQuestion = body.currentQuestion;
    var currentField = body.currentField;
    var allResponses = body.allResponses || {};
    var chatHistory = body.chatHistory || [];
    var flowQuestions = body.flowQuestions || [];

  var apiKey = process.env.ANTHROPIC_API_KEY;
    if (!apiKey) {
          return new Response(JSON.stringify({ error: "No API key" }), {
                  status: 500,
                  headers: { "Content-Type": "application/json" }
          });
    }

  var responseSummary = Object.entries(allResponses)
      .map(function(e) { return e[0] + ": " + e[1]; })
      .join("\n");

  var qList = flowQuestions.map(function(q, i) {
        return (i + 1) + ". [" + q.f + "] " + q.q;
  }).join("\n");

  var systemPrompt = [
        "You are a warm, friendly medical intake assistant for Global Neuro & Spine Institute.",
        "You are having a FAST-PACED natural voice conversation. Think of how a friendly nurse chats with patients - quick, warm, efficient.",
        "",
        "CURRENT FIELD: " + (currentField || "none"),
        "CURRENT QUESTION TOPIC: " + (currentQuestion || "none"),
        "",
        "DATA COLLECTED SO FAR:",
        responseSummary || "(nothing yet)",
        "",
        "REMAINING QUESTIONS TO ASK:",
        qList || "(none)",
        "",
        "CRITICAL RULES:",
        "",
        "1. YOUR REPLY IS THE ENTIRE SPOKEN RESPONSE. The system will speak ONLY what you put in 'reply'. So your reply must include BOTH your acknowledgment AND the next question when advancing.",
        "",
        "2. BE FAST AND NATURAL. Like a real conversation:",
        "   - Good: 'Got it, Marc! And what is your date of birth?'",
        "   - Good: 'Okay great. How tall are you?'",
        "   - Bad: 'Thank you for providing that information. I have recorded your name as Marc. Now, I would like to ask you about your date of birth. Could you please tell me your date of birth?'",
        "",
        "3. NEVER REPEAT A QUESTION the patient already answered. If they gave their name, do NOT ask for their name again. Move forward.",
        "",
        "4. NEVER RE-ASK THE SAME QUESTION YOU JUST ASKED unless you need clarification. If you asked for their DOB and they answered, acknowledge and move to the NEXT question.",
        "",
        "5. IF THE PATIENT ANSWERS MULTIPLE QUESTIONS AT ONCE, capture ALL the data and skip ahead to the next unanswered question. For example if they say 'I am Marc Smith, born January 5 1980, I am 5 foot 10', capture name, DOB, and height, then ask for weight.",
        "",
        "6. CORRECTIONS: If the patient says anything like 'that is wrong', 'you misspelled', 'go back', 'not correct', 'actually it is...' - set action to 'stay', fix the data in updates, and ask them to confirm or continue. NEVER advance when they are correcting something.",
        "",
        "7. KEEP REPLIES SHORT. Max 1-2 sentences. These are spoken aloud. Brevity is key.",
        "",
        "8. USE THEIR NAME once you know it. Be warm but not slow.",
        "",
        "9. For yes/no questions, if they answer yes or no, just capture it and immediately transition to the next question. Do not over-elaborate.",
        "",
        "10. SPELLING: If someone spells out letters like M-A-R-C or 'M A R C' or 'M as in Mary, A, R, C', assemble into: Marc",
        "",
        "RESPOND WITH ONLY A JSON OBJECT:",
        "{",
        "  \"action\": \"advance\" or \"stay\",",
        "  \"updates\": { \"field_name\": \"value\" },",
        "  \"reply\": \"Your full spoken response including next question if advancing\",",
        "  \"skipTo\": \"field_name\" or null",
        "}",
        "",
        "ACTION MEANINGS:",
        "- advance: Patient answered. Put data in updates. Your reply MUST include the next question naturally. skipTo = field name to jump to if skipping questions, or null for next in line.",
        "- stay: Either correcting data, need clarification, or off-topic chat. Stay on current question. Reply should address their concern and re-ask if needed.",
        "",
        "RESPOND WITH ONLY THE JSON. No markdown. No backticks. No extra text."
      ].join("\n");

  var claudeMessages = [];
    var hist = chatHistory.slice(-10);
    for (var i = 0; i < hist.length; i++) {
          var m = hist[i];
          var role = m.role === "user" ? "user" : "assistant";
          if (claudeMessages.length > 0 && claudeMessages[claudeMessages.length - 1].role === role) {
                  claudeMessages[claudeMessages.length - 1].content += "\n" + m.text;
          } else {
                  claudeMessages.push({ role: role, content: m.text });
          }
    }

  if (claudeMessages.length === 0 || claudeMessages[claudeMessages.length - 1].role !== "user") {
        claudeMessages.push({ role: "user", content: message });
  } else {
        claudeMessages[claudeMessages.length - 1].content += "\n" + message;
  }

  if (claudeMessages.length > 0 && claudeMessages[0].role !== "user") {
        claudeMessages.shift();
  }

  try {
        var response = await fetch("https://api.anthropic.com/v1/messages", {
                method: "POST",
                headers: {
                          "Content-Type": "application/json",
                          "x-api-key": apiKey,
                          "anthropic-version": "2023-06-01"
                },
                body: JSON.stringify({
                          model: "claude-sonnet-4-20250514",
                          max_tokens: 300,
                          system: systemPrompt,
                          messages: claudeMessages
                })
        });

      if (!response.ok) {
              var errText = await response.text();
              console.error("Anthropic error:", errText);
              return new Response(JSON.stringify({ error: "AI failed: " + response.status }), {
                        status: 500,
                        headers: { "Content-Type": "application/json" }
              });
      }

      var data = await response.json();
        var content = data.content[0].text.trim();

      if (content.startsWith("```")) {
              content = content.replace(/^```json?\n?/, "").replace(/\n?```$/, "").trim();
      }

      var parsed;
        try {
                parsed = JSON.parse(content);
        } catch (pe) {
                console.error("JSON parse error:", content);
                var jsonMatch = content.match(/\{[\s\S]*\}/);
                if (jsonMatch) {
                          parsed = JSON.parse(jsonMatch[0]);
                } else {
                          throw new Error("Could not parse AI response");
                }
        }

      if (!parsed.action) parsed.action = "advance";
        if (!parsed.updates) parsed.updates = {};
        if (!parsed.reply) parsed.reply = "Got it.";

      return new Response(JSON.stringify(parsed), {
              headers: { "Content-Type": "application/json" }
      });

  } catch (e) {
        console.error("Chat route error:", e);
        return new Response(JSON.stringify({ error: "Failed: " + e.message }), {
                status: 500,
                headers: { "Content-Type": "application/json" }
        });
  }
}
