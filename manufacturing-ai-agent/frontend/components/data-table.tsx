"use client";
import {
  Table,
  TableHeader,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
} from "@/components/ui/table";
import { fmt } from "@/lib/api";
export default function DataTable({
  rows,
}: {
  rows: Record<string, unknown>[];
}) {
  if (!rows.length)
    return (
      <div className="note">
        No records in this scope. Missing observations have not been filled with
        zero.
      </div>
    );
  const keys = Object.keys(rows[0]);
  return (
    <div className="overflow-auto">
      <Table>
        <TableHeader>
          <TableRow>
            {keys.map((k) => (
              <TableHead key={k}>{k.replaceAll("_", " ")}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r, i) => (
            <TableRow key={i}>
              {keys.map((k) => (
                <TableCell key={k}>{fmt(r[k])}</TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
