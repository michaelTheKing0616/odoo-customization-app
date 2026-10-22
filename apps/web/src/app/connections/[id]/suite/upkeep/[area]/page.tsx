"use client";

import { useParams } from "next/navigation";
import { Upkeep } from "@/components/suite/Upkeep";

export default function Page() {
  const { area } = useParams<{ area: string }>();
  return <Upkeep area={area} />;
}
