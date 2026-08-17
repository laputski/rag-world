import { Box, Divider, Link as MuiLink, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { MONO } from "../theme";
import { ATTENTION_ANCHOR, MATURITY_ANCHOR } from "../anchors";

/**
 * How to read the maturity map: the hint behind the (i) beside the title.
 *
 * It used to be one string of seven sentences run together, and it was read the
 * way such a thing always is, which is not at all. A reader opens a hint with
 * one question already formed — what the vertical means, what the pale points
 * are — and a wall makes them search for the answer instead of finding it.
 *
 * So the hint is laid out as a glossary: the term on the left, what it means on
 * the right, and the eye goes down the left column until it meets its question.
 * The chain of levels stands apart at the foot, because it answers a different
 * question, the one about the scale itself, and points at where the rule is
 * given in full.
 */

/**
 * The rows of the glossary, in the order a reader meets the questions.
 *
 * The two axes carry a link onward, because they are the two rows that raise a
 * further question rather than answer one: a hint has room to say what is
 * measured and none to say how. The link stands in the row that raised the
 * question, not at the foot of the hint where it would be found only by
 * somebody already reading to the end.
 */
const ROWS: { key: string; to?: string }[] = [
  { key: "axisX", to: `/article#${MATURITY_ANCHOR}` },
  { key: "axisY", to: `/about#${ATTENTION_ANCHOR}` },
  { key: "colour" },
  { key: "opacity" },
  { key: "inside" },
  { key: "click" },
];

export function HowToRead() {
  const { t } = useTranslation();

  return (
    <Box sx={{ fontSize: "0.8rem" }}>
      <Typography sx={{ fontWeight: 600, fontSize: "0.85rem", mb: 1 }}>
        {t("map.read.title")}
      </Typography>

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: "auto 1fr",
          columnGap: 1.5, rowGap: 0.75,
          alignItems: "baseline",
        }}
      >
        {ROWS.map((row) => (
          <Box key={row.key} sx={{ display: "contents" }}>
            <Typography sx={{ fontSize: "0.78rem", fontWeight: 600, whiteSpace: "nowrap" }}>
              {t(`map.read.${row.key}.term`)}
            </Typography>
            <Typography sx={{ fontSize: "0.78rem", lineHeight: 1.55 }}>
              {t(`map.read.${row.key}.text`)}
              {row.to && (
                <>
                  {" "}
                  <MuiLink component={RouterLink} to={row.to} sx={{ whiteSpace: "nowrap" }}>
                    {t("map.read.how")}
                  </MuiLink>
                </>
              )}
            </Typography>
          </Box>
        ))}
      </Box>

      <Divider sx={{ my: 1.25 }} />

      <Typography sx={{ fontSize: "0.72rem", fontWeight: 600, mb: 0.5 }}>
        {t("map.read.chainTitle")}
      </Typography>
      {/*
        The chain is set in the monospaced face and allowed to wrap: it is read
        as a sequence rather than as a sentence, and an even face keeps the
        codes of the levels aligned down the lines.
      */}
      <Typography sx={{ fontFamily: MONO, fontSize: "0.7rem", lineHeight: 1.7, mb: 1 }}>
        {t("map.read.chain")}
      </Typography>

      {/*
        The caveat closes the hint and carries no link onward: where to read
        further is said in the row that raised the question, and a second link
        to the article at the foot would only be a worse copy of the first.
      */}
      <Typography sx={{ fontSize: "0.76rem", lineHeight: 1.55 }}>
        {t("map.read.caveat")}
      </Typography>
    </Box>
  );
}
