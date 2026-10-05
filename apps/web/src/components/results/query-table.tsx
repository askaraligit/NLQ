"use client";

import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { QueryCell, QueryRow } from "@/types/nlq";

type SortDirection = "ascending" | "descending";

type QueryTableProps = {
  columns: Array<{ name: string }>;
  rows: QueryRow[];
};

const PAGE_SIZE = 10;

function cellText(value: QueryCell): string {
  if (value === null) {
    return "—";
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  return String(value);
}

function compareCells(left: QueryCell, right: QueryCell): number {
  if (left === right) {
    return 0;
  }
  if (left === null) {
    return 1;
  }
  if (right === null) {
    return -1;
  }
  const leftNumber = Number(left);
  const rightNumber = Number(right);
  if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) {
    return leftNumber - rightNumber;
  }
  return cellText(left).localeCompare(cellText(right), undefined, { numeric: true, sensitivity: "base" });
}

export function QueryTable({ columns, rows }: Readonly<QueryTableProps>) {
  const [sort, setSort] = useState<{ column: string; direction: SortDirection } | null>(null);
  const [page, setPage] = useState(0);
  const sortedRows = useMemo(() => {
    if (!sort) {
      return rows;
    }
    return [...rows].sort((left, right) => {
      const compared = compareCells(left[sort.column] ?? null, right[sort.column] ?? null);
      return sort.direction === "ascending" ? compared : -compared;
    });
  }, [rows, sort]);
  const totalPages = Math.max(1, Math.ceil(sortedRows.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages - 1);
  const pageRows = sortedRows.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);

  function toggleSort(column: string) {
    setPage(0);
    setSort((current) => {
      if (current?.column !== column) {
        return { column, direction: "ascending" };
      }
      return { column, direction: current.direction === "ascending" ? "descending" : "ascending" };
    });
  }

  if (rows.length === 0) {
    return <p className="py-12 text-center text-sm text-muted-foreground">No rows matched this question.</p>;
  }

  return (
    <div>
      <div className="overflow-x-auto rounded-xl border">
        <table className="w-full min-w-[36rem] border-collapse text-left text-sm">
          <thead className="bg-secondary/60 text-xs text-secondary-foreground">
            <tr>
              {columns.map(({ name }) => {
                const isSorted = sort?.column === name;
                const SortIcon = !isSorted ? ArrowUpDown : sort.direction === "ascending" ? ArrowUp : ArrowDown;
                return (
                  <th key={name} scope="col" className="border-b px-4 py-3 font-medium">
                    <button
                      type="button"
                      onClick={() => toggleSort(name)}
                      className="inline-flex items-center gap-1.5 rounded outline-none hover:text-primary focus-visible:ring-2 focus-visible:ring-ring"
                      aria-label={`Sort by ${name}`}
                    >
                      {name}<SortIcon className="size-3.5" aria-hidden="true" />
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row, index) => (
              <tr key={`${currentPage}-${index}`} className="border-b last:border-b-0 hover:bg-secondary/30">
                {columns.map(({ name }) => <td key={name} className="max-w-80 truncate px-4 py-3.5 text-foreground" title={cellText(row[name] ?? null)}>{cellText(row[name] ?? null)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalPages > 1 ? (
        <div className="mt-4 flex items-center justify-between gap-3 text-xs text-muted-foreground">
          <span>Showing {currentPage * PAGE_SIZE + 1}–{Math.min((currentPage + 1) * PAGE_SIZE, rows.length)} of {rows.length} rows</span>
          <div className="flex gap-1">
            <Button variant="outline" size="sm" onClick={() => setPage((value) => Math.max(0, value - 1))} disabled={currentPage === 0}><ChevronLeft aria-hidden="true" />Previous</Button>
            <Button variant="outline" size="sm" onClick={() => setPage((value) => Math.min(totalPages - 1, value + 1))} disabled={currentPage === totalPages - 1}>Next<ChevronRight aria-hidden="true" /></Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
