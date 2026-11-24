import { Calendar, Pencil, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AcademicYearFormDialog } from "@/components/schools/academic-year-form-dialog";
import { TermFormDialog } from "@/components/schools/term-form-dialog";
import { DeleteConfirmButton } from "@/components/schools/delete-confirm-button";
import { ActivateButton } from "@/components/schools/activate-button";
import { getAcademicYears, getTerms, type AcademicYear, type Term } from "@/lib/schools";
import {
  createAcademicYear,
  updateAcademicYear,
  deleteAcademicYear,
  activateAcademicYear,
  createTerm,
  updateTerm,
  deleteTerm,
  activateTerm,
} from "@/lib/actions/schools";
import { academicYearDefaults, termDefaults } from "@/lib/schools-forms";

function TermRow({ schoolId, term }: { schoolId: string; term: Term }) {
  return (
    <div className="flex items-center justify-between rounded-md bg-muted/50 px-3 py-1.5 text-sm">
      <span>
        {term.sequence}. {term.name}{" "}
        <span className="text-muted-foreground">
          ({term.start_date} – {term.end_date})
        </span>
      </span>
      <div className="flex items-center gap-1">
        {term.is_current && <Badge variant="outline">Current</Badge>}
        {!term.is_current && (
          <ActivateButton label="Activate" action={activateTerm.bind(null, schoolId, term.public_id)} />
        )}
        <TermFormDialog
          trigger={
            <Button variant="ghost" size="icon-sm">
              <Pencil className="h-3.5 w-3.5" />
            </Button>
          }
          title="Edit term"
          defaultValues={{
            name: term.name,
            sequence: term.sequence,
            start_date: term.start_date,
            end_date: term.end_date,
            is_active: term.is_active,
          }}
          action={updateTerm.bind(null, schoolId, term.public_id)}
        />
        <DeleteConfirmButton
          description={`Delete term ${term.name}?`}
          action={deleteTerm.bind(null, schoolId, term.public_id)}
        />
      </div>
    </div>
  );
}

async function YearCard({ schoolId, year }: { schoolId: string; year: AcademicYear }) {
  const terms = await getTerms(year.public_id);

  return (
    <div className="rounded-lg border">
      <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="font-medium">{year.name}</span>
          <span className="text-sm text-muted-foreground">
            {year.start_date} – {year.end_date}
          </span>
          {year.is_current && <Badge variant="outline">Current</Badge>}
          {!year.is_active && <Badge variant="secondary">Inactive</Badge>}
        </div>
        <div className="flex items-center gap-1">
          {!year.is_current && (
            <ActivateButton label="Activate" action={activateAcademicYear.bind(null, schoolId, year.public_id)} />
          )}
          <AcademicYearFormDialog
            trigger={
              <Button variant="ghost" size="icon-sm">
                <Pencil className="h-4 w-4" />
              </Button>
            }
            title="Edit academic year"
            defaultValues={{
              name: year.name,
              start_date: year.start_date,
              end_date: year.end_date,
              is_active: year.is_active,
            }}
            action={updateAcademicYear.bind(null, schoolId, year.public_id)}
          />
          <DeleteConfirmButton
            description={`Delete academic year ${year.name}?`}
            action={deleteAcademicYear.bind(null, schoolId, year.public_id)}
          />
        </div>
      </div>

      {terms !== null && (
        <div className="px-4 py-3">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Terms</p>
            <TermFormDialog
              trigger={
                <button type="button" className="text-xs font-medium text-primary hover:underline">
                  + Add term
                </button>
              }
              title="New term"
              defaultValues={termDefaults}
              action={createTerm.bind(null, schoolId, year.public_id)}
            />
          </div>
          {terms.length === 0 ? (
            <p className="text-sm text-muted-foreground">No terms yet.</p>
          ) : (
            <div className="space-y-1.5">
              {terms.map((term) => (
                <TermRow key={term.public_id} schoolId={schoolId} term={term} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export async function AcademicYearsSection({ schoolId }: { schoolId: string }) {
  const years = await getAcademicYears(schoolId);
  if (years === null) return null;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Academic years</CardTitle>
        <AcademicYearFormDialog
          trigger={
            <Button size="sm" variant="secondary">
              <Plus className="h-4 w-4" />
              New academic year
            </Button>
          }
          title="New academic year"
          defaultValues={academicYearDefaults}
          action={createAcademicYear.bind(null, schoolId)}
        />
      </CardHeader>
      <CardContent>
        {years.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-8 text-center">
            <Calendar className="h-6 w-6 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">No academic years yet</p>
          </div>
        ) : (
          <div className="space-y-4">
            {years.map((year) => (
              <YearCard key={year.public_id} schoolId={schoolId} year={year} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
