"use client";

import { useEffect, useState } from "react";
import { Card, PageHeader } from "@/components/ui/layout-primitives";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { ErrorNotice } from "@/components/ui/ErrorNotice";

type AdminUser = { id: string; email: string; email_verified: boolean; is_superadmin: boolean };

export default function AdminPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"}/api/admin/users`, {
      credentials: "include",
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(await res.text());
        return res.json() as Promise<AdminUser[]>;
      })
      .then(setUsers)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load admin"));
  }, []);

  const columns: DataTableColumn<AdminUser>[] = [
    { id: "email", header: "Email", accessor: (r) => r.email },
    { id: "verified", header: "Verified", accessor: (r) => (r.email_verified ? "Yes" : "No") },
    { id: "super", header: "Superadmin", accessor: (r) => (r.is_superadmin ? "Yes" : "No") },
  ];

  return (
    <div className="space-y-6 p-6">
      <PageHeader title="Admin console" description="Superadmin-only workspace and user management." />
      {error ? <ErrorNotice message={error} /> : null}
      <Card>
        <DataTable columns={columns} rows={users} rowKey={(r) => r.id} />
      </Card>
    </div>
  );
}
