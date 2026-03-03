export async function POST(request) {
  const { message, currentQuestion, currentField, allResponses, chatHistory, flowQuestions } = await request.json();

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    return new Response(JSON.stringify({ error: "No OpenAI API key configured" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  const responseSummary = Object.entries(allResponses || {})
    .map(function(entry) { return entry[0] + ": " + entry[1]; })
    .join("\n");

  const recentChat = (chatHistory || []).slice(-10).map(function(m) {
    return (m.role === "user" ? "Patient" : "Assistant") + ": " + m.text;
  }).join("\n");

  var qList = (flowQuestions || []).map(function(q, i) {
    return (i + 1) + ". [" + q.f + "] " + q.q;
  }).join("\n");

  var systemPrompt = "You are a friendly, warm medical intake assistant for Global Neuro & Spine Institute. You are having a natural voice conversation with a patient to collect their intake information.\n\nCURRENT STATE:\n- Current question being asked: \"" + (currentQuestion || "none") + "\"\n- Current field to fill: \"" + (currentField || "none") + "\"\n- Data collected so far:\n" + (responseSummary || "Nothing yet") + "\n\nRECENT CONVERSATION:\n" + (recentChat || "Just started") + "\n\nREMAINING QUESTIONS TO ASK (in order):\n" + qList + "\n\nYOUR JOB:\nAnalyze the patient's message and determine what to do. You must respond with valid JSON only.\n\nRULES FOR UNDERSTANDING THE PATIENT:\n1. CORRECTIONS: If the patient says things like \"that's wrong\", \"no my name is spelled...\", \"go back\", \"I said...\", \"actually it's...\", \"not right\", \"you got that wrong\", \"let me correct that\", \"that's not what I said\" they are trying to fix a previous answer. Figure out WHICH field they want to correct from context. If they say \"my name is spelled M-A-R-C\" after giving their name, the corrected field is \"full_name\" and the value is \"Marc\" (assemble spelled letters into the name).\n2. SPELLING: If the patient spells something out letter by letter (like \"M-A-R-C-O-S\" or \"M A R C O S\" or \"capital M, a, r, c\"), assemble the letters into the correct word/name.\n3. CLARIFICATIONS: If the patient asks \"what do you mean?\" or \"can you repeat that?\", re-ask the current question in different words.\n4. MULTI-PART ANSWERS: If the patient gives info that answers multiple questions at once (like \"My name is John Smith, born January 5 1980\"), extract all the answers.\n5. CONVERSATIONAL: If the patient says something conversational like \"hello\" or \"how are you\", respond naturally but guide them back to the current question.\n6. NORMAL ANSWER: If the patient simply answers the current question, accept it and move on.\n7. YES/NO INTERPRETATION: For yes/no questions, interpret \"yeah\", \"yep\", \"sure\", \"nah\", \"nope\", \"not really\" etc. as Yes or No.\n8. SCALE INTERPRETATION: For pain scale questions, extract the number. \"about a 7\" = \"7\", \"maybe 8 or 9\" = \"8\".\n\nRESPOND WITH THIS EXACT JSON FORMAT:\n{\n  \"action\": \"accept\" | \"correct\" | \"clarify\" | \"multi\" | \"conversational\",\n  \"updates\": { \"field_name\": \"value\" },\n  \"reply\": \"Your natural spoken response to the patient\",\n  \"moveToField\": \"field_name_to_go_to_next_or_null\"\n}\n\n- \"accept\": patient answered the current question normally. Put the answer in updates with the current field name.\n- \"correct\": patient is correcting a previous answer. Put the corrected field+value in updates. Set moveToField to the field AFTER the corrected one so we continue from there, OR null to stay on current question.\n- \"clarify\": patient needs the question repeated or explained. No updates. Reply with a rephrased question.\n- \"multi\": patient answered multiple questions at once. Put ALL extracted answers in updates. Set moveToField to the next unanswered field.\n- \"conversational\": patient said something off-topic. No updates. Reply naturally and re-ask the current question.\n\nIMPORTANT: Your \"reply\" should sound like a real person talking. Warm, brief, natural. Use the patient's name if you know it. Acknowledge corrections gracefully (\"Oh sorry about that! I have updated your name to Marc.\"). Keep it concise since this will be spoken aloud.";

  try {
    var response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + apiKey,
      },
      body: JSON.stringify({
        model: "gpt-4o-mini",
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: message },
        ],
        temperature: 0.3,
        max_tokens: 500,
        response_format: { type: "json_object" },
      }),
    });

    if (!response.ok) {
      var err = await response.text();
      console.error("OpenAI error:", err);
      return new Response(JSON.stringify({ error: "AI processing failed" }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      });
    }

    var data = await response.json();
    var content = data.choices[0].message.content;
    var parsed = JSON.parse(content);

    return new Response(JSON.stringify(parsed), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (e) {
    console.error("Chat API error:", e);
    return new Response(JSON.stringify({ error: "Failed to process message" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}
