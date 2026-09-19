import "./tabletop.css";

export const metadata = {
  title: "Tabletop Stop | Dishes for the Well-Dressed Table",
  description:
    "Hand-picked dinnerware, serveware, glassware and table accents from our home showroom. Shop online or book a private showroom visit.",
  openGraph: {
    title: "Tabletop Stop",
    description: "Dishes for the well-dressed table. Shop online or visit our home showroom by appointment.",
    type: "website",
  },
};

export default function TabletopLayout({ children }) {
  return (
    <>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      <link
        rel="stylesheet"
        href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,300;1,400&family=Jost:wght@300;400;500&display=swap"
      />
      {children}
    </>
  );
}
