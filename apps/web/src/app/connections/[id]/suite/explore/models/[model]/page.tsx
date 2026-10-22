"use client";

import { useParams } from "next/navigation";
import { ExploreModel } from "@/components/suite/Explore";

export default function Page() {
  const { model } = useParams<{ model: string }>();
  return <ExploreModel model={decodeURIComponent(model)} />;
}
