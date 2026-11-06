import "./globals.css";
import QueryProvider from "@/lib/query/QueryProvider";

export const metadata = { title: "JinDou Cloud" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="bg-page text-ink antialiased">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}