"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Getting Started moved into /governance as a section (see that page's module docstring
 * for why -- it and Governance were two nav entries people kept mistaking for duplicates).
 * This redirect exists only so an old bookmark or link to /guide still lands somewhere
 * useful instead of a 404.
 */
export default function GuideRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/governance");
  }, [router]);
  return null;
}
