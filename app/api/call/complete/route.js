import Anthropic from '@anthropic-ai/sdk';
import PDFDocument from 'pdfkit';
import { Resend } from 'resend';

export const runtime = 'nodejs';
export const maxDuration = 60;

const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
const resend = new Resend(process.env.RESEND_API_KEY);

async function parseTranscript(transcript) {
  const messages = transcript
    .map(t => `${t.role === 'agent' ? 'Sarah' : 'Patient'}: ${t.message}`)
    .join('\n');

  const response = await anthropic.messages.create({
    model: 'claude-haiku-4-5',
    max_tokens: 1500,
    messages: [{
      role: 'user',
      content: `You are extracting structured patient intake data from a voice call transcript.
Extract every piece of information the patient provided. Return ONLY a JSON object — no markdown, no backticks.

Transcript:
${messages}

Return this exact JSON structure (use null for anything not mentioned):
{
  "full_name": null,
  "dob": null,
  "height": null,
  "weight": null,
  "visit_type": "new_patient or follow_up",
  "chief_complaint": null,
  "pain_location": null,
  "pain_radiation": null,
  "pain_worse": null,
  "pain_better": null,
  "pain_description": null,
  "pain_severity": null,
  "cause_of_pain": null,
  "date_of_injury": null,
  "prior_pain": null,
  "treatments": null,
  "medications": null,
  "allergies": null,
  "medical_conditions": null,
  "surgeries": null,
  "hospitalizations": null,
  "family_history": null,
  "marital_status": null,
  "employment": null,
  "smoking": null,
  "alcohol": null,
  "disability": null,
  "ros_constitutional": null,
  "ros_cardiovascular": null,
  "ros_neurological": null,
  "ros_musculoskeletal": null,
  "ros_psychiatric": null,
  "ros_other": null,
  "pregnant": null,
  "had_procedure": null,
  "procedure_relief": null,
  "new_medications": null,
  "new_conditions": null,
  "family_changes": null,
  "social_changes": null,
  "verbal_consent": null,
  "call_date": "${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}"
}`
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
    doc.fillColor(LIGHT).fontSize(10).text(`Date: ${data.call_date || new Date().toLocaleDateString()}`, 55, y + 36, { align: 'right', width: pageWidth });
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
      if (inline) {
        doc.fontSize(9).font('Helvetica-Bold').fillColor(GRAY).text(label + ': ', 55, y, { continued: true, width: 160 });
        doc.font('Helvetica').fillColor(BLACK).text(String(value));
        y += 16;
      } else {
        doc.fontSize(9).font('Helvetica-Bold').fillColor(GRAY).text(label + ':', 55, y);
        y += 13;
        doc.font('Helvetica').fillColor(BLACK).fontSize(9).text(String(value), 65, y, { width: pageWidth - 15 });
        y += doc.heightOfString(String(value), { width: pageWidth - 15 }) + 8;
      }
    }

    sectionTitle('PATIENT INFORMATION');
    field('Name', data.full_name, true);
    field('Date of Birth', data.dob, true);
    field('Height', data.height, true);
    field('Weight', data.weight, true);
    field('Visit Type', data.visit_type === 'follow_up' ? 'Follow-Up Visit' : 'New Patient', true);
    field('Marital Status', data.marital_status, true);
    field('Employment', data.employment, true);
    y += 8;

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
    y += 8;

    if (data.visit_type === 'follow_up') {
      sectionTitle('LAST VISIT UPDATES');
      field('Had Procedure', data.had_procedure, true);
      field('Procedure Relief', data.procedure_relief, true);
      field('New Medications', data.new_medications);
      field('New Conditions', data.new_conditions);
      field('Family Changes', data.family_changes);
      field('Social Changes', data.social_changes);
      y += 8;
    }

    sectionTitle('MEDICATIONS & ALLERGIES');
    field('Current Medications', data.medications);
    field('Allergies', data.allergies);
    y += 8;

    if (data.visit_type !== 'follow_up') {
      sectionTitle('MEDICAL HISTORY');
      field('Medical Conditions', data.medical_conditions);
      field('Past Surgeries', data.surgeries);
      field('Past Hospitalizations', data.hospitalizations);
      field('Family History', data.family_history);
      y += 8;

      sectionTitle('SOCIAL HISTORY');
      field('Smoking', data.smoking, true);
      field('Alcohol', data.alcohol, true);
      field('Disability', data.disability, true);
      field('Pregnant', data.pregnant, true);
      y += 8;
    }

    sectionTitle('REVIEW OF SYSTEMS');
    field('Constitutional', data.ros_constitutional);
import PDFDocument from 'pdfkit';
import { Resend } from 'resend';

export const runtime = 'nodejs';
export const maxDuration = 60;

const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
const resend = new Resend(process.env.RESEND_API_KEY);

async function parseTranscript(transcript) {
  const messages = transcript
    .map(t => `${t.role === 'agent' ? 'Sarah' : 'Patient'}: ${t.message}`)
    .join('\n');

  const response = await anthropic.messages.create({
    model: 'claude-haiku-4-5',
    max_tokens: 1500,
    messages: [{
      role: 'user',
      content: `You are extracting structured patient intake data from a voice call transcript.
Extract every piece of information the patient provided. Return ONLY a JSON object — no markdown, no backticks.

Transcript:
${messages}

Return this exact JSON structure (use null for anything not mentioned):
{
  "full_name": null,
  "dob": null,
  "height": null,
  "weight": null,
  "visit_type": "new_patient or follow_up",
  "chief_complaint": null,
  "pain_location": null,
  "pain_radiation": null,
  "pain_worse": null,
  "pain_better": null,
  "pain_description": null,
  "pain_severity": null,
  "cause_of_pain": null,
  "date_of_injury": null,
  "prior_pain": null,
  "treatments": null,
  "medications": null,
  "allergies": null,
  "medical_conditions": null,
  "surgeries": null,
  "hospitalizations": null,
  "family_history": null,
  "marital_status": null,
  "employment": null,
  "smoking": null,
  "alcohol": null,
  "disability": null,
  "ros_constitutional": null,
  "ros_cardiovascular": null,
  "ros_neurological": null,
  "ros_musculoskeletal": null,
  "ros_psychiatric": null,
  "ros_other": null,
  "pregnant": null,
  "had_procedure": null,
  "procedure_relief": null,
  "new_medications": null,
  "new_conditions": null,
  "family_changes": null,
  "social_changes": null,
  "verbal_consent": null,
  "call_date": "${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}"
}`
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
    doc.fillColor(LIGHT).fontSize(10).text(`Date: ${data.call_date || new Date().toLocaleDateString()}`, 55, y + 36, { align: 'right', width: pageWidth });
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
      if (inline) {
        doc.fontSize(9).font('Helvetica-Bold').fillColor(GRAY).text(label + ': ', 55, y, { continued: true, width: 160 });
        doc.font('Helvetica').fillColor(BLACK).text(String(value));
        y += 16;
      } else {
        doc.fontSize(9).font('Helvetica-Bold').fillColor(GRAY).text(label + ':', 55, y);
        y += 13;
        doc.font('Helvetica').fillColor(BLACK).fontSize(9).text(String(value), 65, y, { width: pageWidth - 15 });
        y += doc.heightOfString(String(value), { width: pageWidth - 15 }) + 8;
      }
    }

    sectionTitle('PATIENT INFORMATION');
    field('Name', data.full_name, true);
    field('Date of Birth', data.dob, true);
    field('Height', data.height, true);
    field('Weight', data.weight, true);
    field('Visit Type', data.visit_type === 'follow_up' ? 'Follow-Up Visit' : 'New Patient', true);
    field('Marital Status', data.marital_status, true);
    field('Employment', data.employment, true);
    y += 8;

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
    y += 8;

    if (data.visit_type === 'follow_up') {
      sectionTitle('LAST VISIT UPDATES');
      field('Had Procedure', data.had_procedure, true);
      field('Procedure Relief', data.procedure_relief, true);
      field('New Medications', data.new_medications);
      field('New Conditions', data.new_conditions);
      field('Family Changes', data.family_changes);
      field('Social Changes', data.social_changes);
      y += 8;
    }

    sectionTitle('MEDICATIONS & ALLERGIES');
    field('Current Medications', data.medications);
    field('Allergies', data.allergies);
    y += 8;

    if (data.visit_type !== 'follow_up') {
      sectionTitle('MEDICAL HISTORY');
      field('Medical Conditions', data.medical_conditions);
      field('Past Surgeries', data.surgeries);
      field('Past Hospitalizations', data.hospitalizations);
      field('Family History', data.family_history);
      y += 8;

      sectionTitle('SOCIAL HISTORY');
      field('Smoking', data.smoking, true);
      field('Alcohol', data.alcohol, true);
      field('Disability', data.disability, true);
      field('Pregnant', data.pregnant, true);
      y += 8;
    }

    sectionTitle('REVIEW OF SYSTEMS');
    field('Constitutional', data.ros_constitutional);
    field('Cardiovascular', data.ros_cardiovascular);
    field('Neurological', data.ros_neurological);
    field('Musculoskeletal', data.ros_musculoskeletal);
    field('Psychiatric', data.ros_psychiatric);
    field('Other', data.ros_other);
    y += 8;

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

    console.log(`[call/complete] Processing call ${conversationId}, ${transcript.length} messages`);

    const intakeData = await parseTranscript(transcript);
    const pdfBuffer = await generatePDF(intakeData);

    const practiceEmail = process.env.PRACTICE_EMAIL || 'intake@voiceintake.com';
    const patientName = intakeData.full_name || 'Unknown Patient';
    const today = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

    await resend.emails.send({
      from: 'VoiceIntake <intake@voiceintake.com>',
      to: practiceEmail,
      subject: `Intake Complete: ${patientName} — ${today}`,
      html: `<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
        <div style="background:#1B4F8A;padding:24px 32px;border-radius:8px 8px 0 0">
          <h1 style="color:white;margin:0;font-size:22px">VoiceIntake</h1>
          <p style="color:#BDD7EE;margin:4px 0 0">New Intake Completed</p>
        </div>
        <div style="background:#f8f9fa;padding:24px 32px;border:1px solid #e0e0e0;border-top:none">
          <p style="color:#333;font-size:15px">A patient intake call has been completed.</p>
          <table style="width:100%;border-collapse:collapse;margin:16px 0">
            <tr><td style="padding:8px 0;color:#666;font-size:13px;width:140px">Patient</td><td style="padding:8px 0;color:#1a1a1a;font-size:13px;font-weight:bold">${patientName}</td></tr>
            <tr><td style="padding:8px 0;color:#666;font-size:13px">Date</td><td style="padding:8px 0;color:#1a1a1a;font-size:13px">${today}</td></tr>
            <tr><td style="padding:8px 0;color:#666;font-size:13px">Visit Type</td><td style="padding:8px 0;color:#1a1a1a;font-size:13px">${intakeData.visit_type === 'follow_up' ? 'Follow-Up' : 'New Patient'}</td></tr>
            <tr><td style="padding:8px 0;color:#666;font-size:13px">Chief Complaint</td><td style="padding:8px 0;color:#1a1a1a;font-size:13px">${intakeData.chief_complaint || 'See attached'}</td></tr>
            <tr><td style="padding:8px 0;color:#666;font-size:13px">Call Duration</td><td style="padding:8px 0;color:#1a1a1a;font-size:13px">${Math.floor(callDuration/60)}m ${callDuration%60}s</td></tr>
          </table>
          <p style="color:#555;font-size:13px">The full intake summary is attached as a PDF.</p>
        </div>
        <div style="background:#eef2f7;padding:14px 32px;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 8px 8px">
          <p style="color:#888;font-size:11px;margin:0">Automated message from VoiceIntake. Verbal consent was obtained and the call was recorded.</p>
        </div>
      </div>`,
      attachments: [{
        filename: `intake-${patientName.replace(/\s+/g,'-').toLowerCase()}-${Date.now()}.pdf`,
        content: pdfBuffer.toString('base64'),
      }]
    });

    console.log(`[call/complete] Email sent to ${practiceEmail} for ${patientName}`);
    return Response.json({ success: true, patient: patientName, email_sent_to: practiceEmail });

  } catch (error) {
    console.error('[call/complete] Error:', error);
    return Response.json({ error: error.message }, { status: 500 });
  }
}
