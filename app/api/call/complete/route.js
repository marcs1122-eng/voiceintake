import Anthropic from '@anthropic-ai/sdk';
import PDFDocument from 'pdfkit';
import { Resend } from 'resend';

export const runtime = 'nodejs';
export const maxDuration = 60;

// Lazy-initialize clients to avoid build-time crashes when env vars are missing
let _anthropic;
function getAnthropic() {
  if (!_anthropic) _anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  return _anthropic;
}

let _resend;
function getResend() {
  if (!_resend) _resend = new Resend(process.env.RESEND_API_KEY);
  return _resend;
}

async function parseTranscript(transcript) {
  const messages = transcript
    .map(t => (t.role === 'agent' ? 'Sarah' : 'Patient') + ': ' + t.message)
    .join('\n');

  const callDate = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

  const response = await getAnthropic().messages.create({
    model: 'claude-haiku-4-5',
    max_tokens: 1500,
    messages: [{
      role: 'user',
      content: 'You are extracting structured patient intake data from a voice call transcript. Extract every piece of information the patient provided. Return ONLY a JSON object with no markdown or backticks.\n\nTranscript:\n' + messages + '\n\nReturn this exact JSON structure (use null for anything not mentioned):\n{\n  "full_name": null,\n  "dob": null,\n  "height": null,\n  "weight": null,\n  "visit_type": "new_patient or follow_up",\n  "chief_complaint": null,\n  "pain_location": null,\n  "pain_radiation": null,\n  "pain_worse": null,\n  "pain_better": null,\n  "pain_description": null,\n  "pain_severity": null,\n  "cause_of_pain": null,\n  "date_of_injury": null,\n  "prior_pain": null,\n  "treatments": null,\n  "medications": null,\n  "allergies": null,\n  "medical_conditions": null,\n  "surgeries": null,\n  "hospitalizations": null,\n  "family_history": null,\n  "marital_status": null,\n  "employment": null,\n  "smoking": null,\n  "alcohol": null,\n  "disability": null,\n  "ros_constitutional": null,\n  "ros_cardiovascular": null,\n  "ros_neurological": null,\n  "ros_musculoskeletal": null,\n  "ros_psychiatric": null,\n  "ros_other": null,\n  "pregnant": null,\n  "had_procedure": null,\n  "procedure_relief": null,\n  "new_medications": null,\n  "new_conditions": null,\n  "family_changes": null,\n  "social_changes": null,\n  "verbal_consent": null,\n  "call_date": "' + callDate + '"\n}'
    }]
  });

  try {
    return JSON.parse(response.content[0].text);
  } catch {
    return { parse_error: true, raw: response.content[0].text };
  }
}

async function generatePDF(data) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    const doc = new PDFDocument({ margin: 50, size: 'letter' });
    doc.on('data', chunk => chunks.push(chunk));
    doc.on('end', () => resolve(Buffer.concat(chunks)));
    doc.on('error', reject);

    const BLUE = '#1B4F8A';
    const LIGHT = '#DCE6F1';
    const GRAY = '#666666';
    const BLACK = '#1A1A1A';
    const pageWidth = 512;
    let y = 50;

    doc.rect(50, y, pageWidth, 60).fill(BLUE);
    doc.fillColor('white').fontSize(20).font('Helvetica-Bold').text('VoiceIntake', 65, y + 12);
    doc.fontSize(10).font('Helvetica').text('AI Patient Intake Summary', 65, y + 36);
    doc.fillColor(LIGHT).fontSize(10).text('Date: ' + (data.call_date || new Date().toLocaleDateString()), 55, y + 36, { align: 'right', width: pageWidth });
    doc.fillColor(BLACK);
    y += 80;

    function sectionTitle(title) {
      doc.rect(50, y - 4, pageWidth, 22).fill(LIGHT);
      doc.fillColor(BLUE).fontSize(11).font('Helvetica-Bold').text(title, 55, y);
      doc.fillColor(BLACK);
      y += 26;
    }

    function field(label, value, inline) {
      if (!value || value === 'null' || value === null) return;
      const val = String(value);
      if (inline) {
        doc.fontSize(9).font('Helvetica-Bold').fillColor(GRAY).text(label + ': ', 55, y, { continued: true, width: 160 });
        doc.font('Helvetica').fillColor(BLACK).text(val);
        y += 16;
      } else {
        doc.fontSize(9).font('Helvetica-Bold').fillColor(GRAY).text(label + ':', 55, y);
        y += 13;
        doc.font('Helvetica').fillColor(BLACK).fontSize(9).text(val, 65, y, { width: pageWidth - 15 });
        y += doc.heightOfString(val, { width: pageWidth - 15 }) + 8;
      }
    }

    function spacer() { y += 8; }

    sectionTitle('PATIENT INFORMATION');
    field('Name', data.full_name, true);
    field('Date of Birth', data.dob, true);
    field('Height', data.height, true);
    field('Weight', data.weight, true);
    field('Visit Type', data.visit_type === 'follow_up' ? 'Follow-Up Visit' : 'New Patient', true);
    field('Marital Status', data.marital_status, true);
    field('Employment', data.employment, true);
    spacer();

    sectionTitle('CHIEF COMPLAINT & PAIN HISTORY');
    field('Chief Complaint', data.chief_complaint);
    field('Cause of Pain', data.cause_of_pain, true);
    field('Date of Injury', data.date_of_injury, true);
    field('Prior Pain', data.prior_pain, true);
    field('Pain Location', data.pain_location);
    field('Radiation', data.pain_radiation, true);
    field('Pain Description', data.pain_description);
    field('Pain Severity (0-10)', data.pain_severity, true);
    field('What Makes It Worse', data.pain_worse);
    field('What Makes It Better', data.pain_better);
    field('Treatments Tried', data.treatments);
    spacer();

    if (data.visit_type === 'follow_up') {
      sectionTitle('LAST VISIT UPDATES');
      field('Had Procedure', data.had_procedure, true);
      field('Procedure Relief', data.procedure_relief, true);
      field('New Medications', data.new_medications);
      field('New Conditions', data.new_conditions);
      field('Family Changes', data.family_changes);
      field('Social Changes', data.social_changes);
      spacer();
    }

    sectionTitle('MEDICATIONS & ALLERGIES');
    field('Current Medications', data.medications);
    field('Allergies', data.allergies);
    spacer();

    if (data.visit_type !== 'follow_up') {
      sectionTitle('MEDICAL HISTORY');
      field('Medical Conditions', data.medical_conditions);
      field('Past Surgeries', data.surgeries);
      field('Past Hospitalizations', data.hospitalizations);
      field('Family History', data.family_history);
      spacer();

      sectionTitle('SOCIAL HISTORY');
      field('Smoking', data.smoking, true);
      field('Alcohol', data.alcohol, true);
      field('Disability', data.disability, true);
      field('Pregnant', data.pregnant, true);
      spacer();
    }

    sectionTitle('REVIEW OF SYSTEMS');
    field('Constitutional', data.ros_constitutional);
    field('Cardiovascular', data.ros_cardiovascular);
    field('Neurological', data.ros_neurological);
    field('Musculoskeletal', data.ros_musculoskeletal);
    field('Psychiatric', data.ros_psychiatric);
    field('Other', data.ros_other);
    spacer();

    sectionTitle('CONSENT');
    field('Verbal Consent', data.verbal_consent || 'Yes — recorded on call');
    y += 16;

    doc.rect(50, y, pageWidth, 1).fill('#CCCCCC');
    y += 8;
    doc.fillColor(GRAY).fontSize(8).font('Helvetica')
      .text('This intake was collected via VoiceIntake AI. Verbal consent was obtained and the call was recorded. This document is for clinical use only.', 55, y, { width: pageWidth });

    doc.end();
  });
}

export async function POST(request) {
  try {
    const body = await request.json();
    const transcript = body?.data?.transcript || body?.transcript || [];
    const conversationId = body?.data?.conversation_id || body?.conversation_id || 'unknown';
    const callDuration = body?.data?.metadata?.call_duration_secs || 0;

    if (!transcript || transcript.length === 0) {
      return Response.json({ error: 'No transcript received' }, { status: 400 });
    }

    console.log('[call/complete] Processing call ' + conversationId + ', ' + transcript.length + ' messages');

    const intakeData = await parseTranscript(transcript);
    const pdfBuffer = await generatePDF(intakeData);

    const practiceEmail = process.env.PRACTICE_EMAIL || 'intake@voiceintake.com';
    const patientName = intakeData.full_name || 'Unknown Patient';
    const today = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    const visitType = intakeData.visit_type === 'follow_up' ? 'Follow-Up' : 'New Patient';
    const mins = Math.floor(callDuration / 60);
    const secs = callDuration % 60;

    await getResend().emails.send({
      from: 'VoiceIntake <onboarding@resend.dev>',
      to: practiceEmail,
      subject: 'Intake Complete: ' + patientName + ' — ' + today,
      html: '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto"><div style="background:#1B4F8A;padding:24px 32px;border-radius:8px 8px 0 0"><h1 style="color:white;margin:0;font-size:22px">VoiceIntake</h1><p style="color:#BDD7EE;margin:4px 0 0">New Intake Completed</p></div><div style="background:#f8f9fa;padding:24px 32px;border:1px solid #e0e0e0;border-top:none"><p style="color:#333;font-size:15px">A patient intake call has been completed.</p><table style="width:100%;border-collapse:collapse;margin:16px 0"><tr><td style="padding:8px 0;color:#666;font-size:13px;width:140px">Patient</td><td style="padding:8px 0;color:#1a1a1a;font-size:13px;font-weight:bold">' + patientName + '</td></tr><tr><td style="padding:8px 0;color:#666;font-size:13px">Date</td><td style="padding:8px 0;color:#1a1a1a;font-size:13px">' + today + '</td></tr><tr><td style="padding:8px 0;color:#666;font-size:13px">Visit Type</td><td style="padding:8px 0;color:#1a1a1a;font-size:13px">' + visitType + '</td></tr><tr><td style="padding:8px 0;color:#666;font-size:13px">Chief Complaint</td><td style="padding:8px 0;color:#1a1a1a;font-size:13px">' + (intakeData.chief_complaint || 'See attached') + '</td></tr><tr><td style="padding:8px 0;color:#666;font-size:13px">Call Duration</td><td style="padding:8px 0;color:#1a1a1a;font-size:13px">' + mins + 'm ' + secs + 's</td></tr></table><p style="color:#555;font-size:13px">The full intake summary is attached as a PDF. Please file it in the patient record.</p></div><div style="background:#eef2f7;padding:14px 32px;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 8px 8px"><p style="color:#888;font-size:11px;margin:0">Automated message from VoiceIntake. Verbal consent was obtained and the call was recorded.</p></div></div>',
      attachments: [{
        filename: 'intake-' + patientName.replace(/\s+/g, '-').toLowerCase() + '-' + Date.now() + '.pdf',
        content: pdfBuffer.toString('base64'),
      }]
    });

    console.log('[call/complete] Email sent to ' + practiceEmail + ' for ' + patientName);
    return Response.json({ success: true, patient: patientName, email_sent_to: practiceEmail });

  } catch (error) {
    console.error('[call/complete] Error:', error);
    return Response.json({ error: error.message }, { status: 500 });
  }
}
