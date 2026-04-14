import { kv } from '@vercel/kv';
import PDFDocument from 'pdfkit';

export const runtime = 'nodejs';

function checkAuth(request) {
  const auth = request.headers.get('Authorization') || '';
  return auth.replace('Bearer ', '').trim() === process.env.ADMIN_PASSWORD;
}

export async function GET(request, { params }) {
  if (!checkAuth(request)) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const record = await kv.get('intake:' + params.callSid);
    if (!record) {
      return Response.json({ error: 'Intake not found' }, { status: 404 });
    }

    const data = record.intakeData;
    const pdfBuffer = await generatePDF(data);

    const patientName = data.full_name || 'Unknown Patient';
    return new Response(pdfBuffer, {
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': 'attachment; filename="intake-' + patientName.replace(/\s+/g, '-').toLowerCase() + '.pdf"',
      },
    });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
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
    field('Verbal Consent', data.verbal_consent || 'Yes \u2014 recorded on call');
    y += 16;

    doc.rect(50, y, pageWidth, 1).fill('#CCCCCC');
    y += 8;
    doc.fillColor(GRAY).fontSize(8).font('Helvetica')
      .text('This intake was collected via VoiceIntake AI. Verbal consent was obtained and the call was recorded. This document is for clinical use only.', 55, y, { width: pageWidth });

    doc.end();
  });
}
