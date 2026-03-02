export const metadata = {
  title: "VoiceIntake — AI Patient Intake",
  description: "Complete your medical intake by simply having a conversation.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, padding: 0 }}>{children}</body>
    </html>
  );
}
