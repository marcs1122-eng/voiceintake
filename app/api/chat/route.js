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
    "You are a friendly medical intake assistant for Global Neuro & Spine Institute.",
    "You are having a natural voice conversation with a patient.",
    "",
    "CURRENT FIELD: " + (currentField || "none"),
    "CURRENT QUESTION: " + (currentQuestion || "none"),
    "",
    "DATA COLLECTED SO FAR:",
    responseSummary || "(nothing yet)",
    "",
    "REMAINING QUESTIONS:",
    qList || "(none)",
    "",
    "INSTRUCTIONS:",
    "Analyze the patient message and respond with ONLY a JSON object.",
    "",
    "DETECTING CORRECTIONS (THIS IS CRITICAL):",
    "If the patient says ANYTHING like:",
    "- \"you spelled my name wrong\"",
    "- \"that is not right\"",
    "- \"no, my name is...\"",
    "- \"actually it is...\"",
    "- \"you got that wrong\"",
    "- \"that is not what I said\"",
    "- \"go back\"",
    "- \"let me correct that\"",
    "- \"wrong\"",
    "- \"not correct\"",
    "- \"misspelled\"",
    "- \"spelled wrong\"",
    "Then the action MUST be \"correct\" or \"clarify\".",
    "If they tell you what the correct value is, use \"correct\" and include the fix in updates.",
    "If they just say it is wrong but do NOT give the correct value, use \"clarify\" and ASK them for the correct value.",
    "NEVER use \"accept\" when the patient is complaining about an error.",
    "",
    "SPELLING OUT LETTERS:",
    "If someone spells letter by letter like M-A-R-C or M A R C, assemble into: Marc",
    "",
    "JSON FORMAT (respond with ONLY this, no other text):",
    "{",
    "  \"action\": \"accept\" or \"correct\" or \"clarify\" or \"multi\" or \"conversational\",",
    "  \"updates\": { \"field_name\": \"value\" } or {},",
    "  \"reply\": \"Your spoken response\",",
    "  \"moveToField\": \"next_field_name\" or null",
    "}",
    "",
    "ACTION DEFINITIONS:",
    "- accept: Patient answered the current question. Put answer in updates with current field. moveToField = null (auto-advance).",
    "- correct: Patient is FIXING a previous answer. Put corrected field and value in updates. moveToField = null (STAY on current question, do NOT advance).",
    "- clarify: Patient needs help or you need more info. No updates. Ask them again. moveToField = null.",
    "- multi: Patient answered several questions at once. Put all in updates. Set moveToField to the next unanswered field name.",
    "- conversational: Off-topic chat. No updates. Reply and re-ask current question.",
    "",
    "IMPORTANT:",
    "- Reply must sound natural and warm, like a real person talking.",
    "- Keep replies SHORT (1-2 sentences) since they are spoken aloud.",
    "- If correcting, say something like \"Oh sorry about that! I have fixed it to [value]. Now, [re-ask current question].\"",
    "- Use the patient name if you know it.",
    "- Respond with ONLY the JSON. No markdown, no backticks, no extra text."
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
        max_tokens: 500,
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
        throw new Error("Could not parse AI response as JSON");
      }
    }

    if (!parsed.action) parsed.action = "accept";
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
