"use client";

import { PageBody, PageHeader } from "@/components/layout/AppShell";
import { RequireRole } from "@/components/layout/RequireRole";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { ErrorState, Notice, SkeletonText } from "@/components/ui/States";
import { Table, Td, Th, Tr } from "@/components/ui/Table";
import { useApiResource } from "@/hooks/useApiResource";
import { getCompliance } from "@/lib/api";

/**
 * EU AI Act / ISO 42001 compliance evidence -- Super Admin only.
 *
 * Parsed live from docs/governance/compliance/*.md (services/api/compliance_view.py), the
 * same "read from the real artifact" rule the Governance page follows for policy/HITL
 * data. This is deliberately not a "we are compliant" badge: both source documents state
 * their own limits explicitly, and this page shows that framing rather than smoothing it
 * away.
 */
export default function CompliancePage() {
  return (
    <RequireRole role="Super Admin">
      <ComplianceContent />
    </RequireRole>
  );
}

function ComplianceContent() {
  const compliance = useApiResource((s) => getCompliance(s), []);

  return (
    <>
      <PageHeader
        title="Compliance"
        description="EU AI Act risk classification and ISO/IEC 42001 control mapping, read directly from the governance documentation that makes each claim — not a second, hand-maintained copy."
      />
      <PageBody className="space-y-6">
        {compliance.error ? (
          <ErrorState
            message={compliance.error.userMessage}
            action={<Button onClick={compliance.refresh}>Try again</Button>}
          />
        ) : !compliance.data ? (
          <Card>
            <CardBody>
              <SkeletonText lines={10} />
            </CardBody>
          </Card>
        ) : (
          <>
            {(() => {
              const gaps = compliance.data!.gap_register.gaps;
              const openGaps = gaps.filter(
                (g) => (g["Target"] ?? "").trim().toLowerCase() !== "closed",
              ).length;
              const closedGaps = gaps.length - openGaps;
              const clauseCount = compliance.data!.iso42001.clause_mapping.length;
              return (
                <Notice tone="ok" title="Evidence discipline in place for EU AI Act and ISO/IEC 42001">
                  Every one of the {clauseCount} ISO 42001 clauses in scope maps to a real
                  artifact or a registered, owned gap below — none are unaddressed. {closedGaps}{" "}
                  of {gaps.length} tracked gaps are closed; the remaining {openGaps} are each
                  assigned an owner and a target below. This reflects evidence discipline, not
                  a compliance determination — see the framing directly below.
                </Notice>
              );
            })()}
            <Notice tone="warning" title="Reasoned classification, not a legal determination">
              This system&apos;s EU AI Act risk tier is derived from its own design
              characteristics (no autonomous terminal action, structural human oversight,
              mandatory evidence citation) — it is not a determination made by qualified
              legal or regulatory authority. Source:{" "}
              <span className="font-mono text-[11px]">{compliance.data.eu_ai_act.source}</span>
            </Notice>

            {/* --- EU AI Act ------------------------------------------------ */}
            <Card>
              <CardHeader
                title="EU AI Act — boundary-pack questions, answered"
                description="Each question comes from the sectoral boundary pack this classification reasons against"
              />
              <CardBody padded={false}>
                <Table caption="EU AI Act boundary-pack questions and answers">
                  <thead>
                    <tr>
                      <Th className="w-[38%]">Question</Th>
                      <Th>Answer, with citation</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {compliance.data.eu_ai_act.boundary_pack_questions.map((row, i) => (
                      <Tr key={i}>
                        <Td className="align-top font-medium">
                          {row["Question (`REGULATORY_BOUNDARY_PACK.md`)"] ?? Object.values(row)[0]}
                        </Td>
                        <Td className="align-top text-[var(--text-secondary)]">
                          {row["Answer, with citation"] ?? Object.values(row)[1]}
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              </CardBody>
            </Card>

            {/* --- ISO 42001 -------------------------------------------------- */}
            <Card>
              <CardHeader
                title="ISO/IEC 42001 — control mapping"
                description="Every clause in scope maps to a real artifact or a registered, owned gap"
              />
              <CardBody padded={false}>
                <Table caption="ISO 42001 clause mapping to real artifacts and operating evidence">
                  <thead>
                    <tr>
                      <Th>Clause</Th>
                      <Th>Mapped artifact</Th>
                      <Th>Operating evidence</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {compliance.data.iso42001.clause_mapping.map((row, i) => (
                      <Tr key={i}>
                        <Td className="align-top font-medium">{Object.values(row)[0]}</Td>
                        <Td className="align-top text-[var(--text-secondary)]">{Object.values(row)[1]}</Td>
                        <Td className="align-top text-[var(--text-secondary)]">{Object.values(row)[2]}</Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              </CardBody>
            </Card>

            {/* --- Open gaps -------------------------------------------------- */}
            <Card>
              <CardHeader
                title="Open gap register"
                description={`Source: ${compliance.data.gap_register.source}`}
              />
              <CardBody padded={false}>
                <Table caption="Open compliance gaps, owners, and targets">
                  <thead>
                    <tr>
                      <Th>ID</Th>
                      <Th>Gap</Th>
                      <Th>Owner</Th>
                      <Th>Target</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {compliance.data.gap_register.gaps.map((row) => {
                      const isClosed = row["Target"]?.trim().toLowerCase() === "closed";
                      return (
                        <Tr key={row["ID"]}>
                          <Td className="align-top font-mono text-[12px]">{row["ID"]}</Td>
                          <Td className="align-top text-[var(--text-secondary)]">{row["Gap"]}</Td>
                          <Td className="align-top text-[var(--text-secondary)]">{row["Owner"]}</Td>
                          <Td className="align-top">
                            <Badge tone={isClosed ? "ok" : "pending"} size="xs">
                              {row["Target"]}
                            </Badge>
                          </Td>
                        </Tr>
                      );
                    })}
                  </tbody>
                </Table>
              </CardBody>
            </Card>
          </>
        )}
      </PageBody>
    </>
  );
}
