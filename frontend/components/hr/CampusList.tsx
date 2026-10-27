"use client";

import { useMemo, useState } from "react";

import { matchesSearch } from "@/lib/search";
import type { Campus, Team } from "@/lib/teams";
import { EmptyPanel } from "@/components/ui/states";
import { ListSearch } from "@/components/ui/list-search";

import { CampusTable } from "./campus-table";

/**
 * The campus table with a local search.
 *
 * A campus answers "which teams sit here?", so the search reaches the team
 * names as well as the campus itself — typing a faculty narrows to the campus
 * that hosts it. Filtering happens after the page's full read, so nothing is
 * hidden because it was on another page.
 */
export function CampusList({
  campuses,
  teams,
}: {
  campuses: Campus[];
  teams: Team[];
}) {
  const [search, setSearch] = useState("");

  const visible = useMemo(
    () =>
      campuses.filter((campus) => {
        const atCampus = teams
          .filter((team) => team.campus === campus.id)
          .map((team) => team.name);
        return matchesSearch(search, [
          campus.name,
          campus.code,
          campus.description,
          campus.is_active ? "active" : "retired",
          ...atCampus,
        ]);
      }),
    [campuses, search, teams]
  );

  return (
    <div className="space-y-4">
      <ListSearch
        value={search}
        onChange={setSearch}
        label="Search campuses"
        placeholder="Search by campus, code, or team"
        className="w-full sm:w-80"
      />
      <CampusTable
        campuses={visible}
        teams={teams}
        empty={
          search ? (
            <EmptyPanel
              title="No campuses match this search"
              description="Try a different campus, code, or team."
            />
          ) : undefined
        }
      />
    </div>
  );
}
