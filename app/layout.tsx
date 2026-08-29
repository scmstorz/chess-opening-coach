import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Chess Opening Coach",
  description: "Lokaler Schacheröffnungs-Trainer mit verifizierten Erklärungen.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="de">
      <body>{children}</body>
    </html>
  );
}

