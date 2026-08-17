import {
  Box, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { FRESHNESS_DAYS, LEVEL_RULES, RULE_VERSION, type RoadSpec } from "../rule.generated";
import { MONO } from "../theme";

/**
 * The maturity rule, shown as a table.
 *
 * The portal demands provenance of every number it prints and owed one for its
 * own scale. The level was stated on every card and drawn along the whole
 * horizontal of the map, and the conditions behind it were told in prose in the
 * article and in a hint over the map: a reader could learn roughly what L4 means
 * and never what it takes.
 *
 * The table is generated from `core/maturity.py` by `make artifacts`, so it is
 * the rule that draws the map rather than a description of it that once was.
 * The names are translated and the codes are not, so the wording lives in the
 * localisation and the structure in the generated module.
 */

export const MATURITY_RULE_ID = "maturity-rule";

function RoadLine({ road }: { road: RoadSpec }) {
  const { t } = useTranslation();
  return (
    <Box sx={{ py: 0.15 }}>
      <Typography component="span" variant="body2">
        {t(`evidenceType.${road.evidence}`, { defaultValue: road.evidence })}
      </Typography>
      {/*
        The class of venue belongs to the road and not to the kind of evidence: a
        publication takes a technology to L1 from a preprint and to L2 only from
        a reviewed venue, and one word for both would make the two rows read the
        same.
      */}
      {road.venue && (
        <Typography component="span" variant="body2" color="text.secondary">
          {" "}({t(`venueClass.${road.venue}`, { defaultValue: road.venue })})
        </Typography>
      )}
      {/*
        The prerequisite stands beside the road rather than in a column of its
        own, because within one level the roads differ in it: the two industrial
        roads to L2 ask for nothing below them, and a column would have to claim
        one answer for all three.
      */}
      {road.requires && (
        <Typography component="span" variant="caption" color="text.secondary">
          {" · "}{t("rule.plusLevel", { level: road.requires })}
        </Typography>
      )}
    </Box>
  );
}

export function MaturityRule() {
  const { t } = useTranslation();

  return (
    <Box id={MATURITY_RULE_ID} sx={{ mt: 3, scrollMarginTop: 80 }}>
      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 0.5 }}>
        {t("rule.title")}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5, fontStyle: "italic" }}>
        {t("rule.intro")}
      </Typography>
      <Typography variant="body2" sx={{ mb: 2, lineHeight: 1.8, maxWidth: "68ch" }}>
        {t("rule.lead")}
      </Typography>

      <TableContainer sx={{ mb: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ width: "12%" }}>{t("rule.colLevel")}</TableCell>
              <TableCell>{t("rule.colRoads")}</TableCell>
              <TableCell sx={{ width: "22%" }}>{t("rule.colBasis")}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {LEVEL_RULES.map((rule) => (
              <TableRow key={rule.level}>
                <TableCell sx={{ fontFamily: MONO, fontWeight: 600, verticalAlign: "top" }}>
                  {rule.level}
                </TableCell>
                <TableCell sx={{ verticalAlign: "top" }}>
                  {rule.roads.length === 0 ? (
                    <Typography variant="body2" color="text.secondary" sx={{ fontStyle: "italic" }}>
                      {t("rule.noCondition")}
                    </Typography>
                  ) : (
                    rule.roads.map((road) => (
                      <RoadLine key={`${road.evidence}-${road.venue ?? ""}`} road={road} />
                    ))
                  )}
                </TableCell>
                <TableCell sx={{ verticalAlign: "top" }}>
                  <Typography
                    variant="body2"
                    color={rule.basis === "manual" ? "text.primary" : "text.secondary"}
                  >
                    {t(`rule.basis.${rule.basis}`)}
                  </Typography>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.8, maxWidth: "68ch" }}>
        {t("rule.bypass")}
      </Typography>
      <Typography variant="body2" sx={{ mb: 3, lineHeight: 1.8, maxWidth: "68ch" }}>
        {t("rule.basisNote")}
      </Typography>

      <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 0.5 }}>
        {t("rule.freshnessTitle")}
      </Typography>
      <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.8, maxWidth: "68ch" }}>
        {t("rule.freshnessIntro")}
      </Typography>

      <TableContainer sx={{ mb: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>{t("rule.colEvidence")}</TableCell>
              <TableCell align="right" sx={{ width: "26%" }}>{t("rule.colDays")}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {Object.entries(FRESHNESS_DAYS).map(([type, days]) => (
              <TableRow key={type}>
                <TableCell>{t(`evidenceType.${type}`, { defaultValue: type })}</TableCell>
                <TableCell align="right" className="tabular">{days}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.8, maxWidth: "68ch" }}>
        {t("rule.confidence")}
      </Typography>
      <Typography variant="caption" color="text.secondary">
        {t("rule.version", { version: RULE_VERSION })}
      </Typography>
    </Box>
  );
}
