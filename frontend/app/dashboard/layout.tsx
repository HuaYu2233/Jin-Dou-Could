"use client";

import Header from "./components/Header";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen flex-col">
      <Header />
      <main className="flex-1 min-h-0 overflow-hidden">{children}</main>
    </div>
  );
}