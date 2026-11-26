import React from "react";
import { LandingNavbar } from "@/components/LandingNavbar";
import { SplitHero } from "@/components/SplitHero";
import { EditorialSections } from "@/components/EditorialSections";

export default function HomePage() {
  return (
    <div className="min-h-screen flex flex-col bg-white">
      <LandingNavbar />
      <main className="flex-1">
        <SplitHero />
        <EditorialSections />
      </main>
    </div>
  );
}
