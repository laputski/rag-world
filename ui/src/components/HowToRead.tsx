import { Box, Divider, Link as MuiLink, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { MONO } from "../theme";

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

/** The rows of the glossary, in the order a reader meets the questions. */
const ROWS = ["axisX", "axisY", "colour", "opacity", "inside", "click"];

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
          <Box key={row} sx={{ display: "contents" }}>
            <Typography sx={{ fontSize: "0.78rem", fontWeight: 600, whiteSpace: "nowrap" }}>
              {t(`map.read.${row}.term`)}
            </Typography>
            <Typography sx={{ fontSize: "0.78rem", lineHeight: 1.55 }}>
              {t(`map.read.${row}.text`)}
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

      <Typography sx={{ fontSize: "0.76rem", lineHeight: 1.55, mb: 0.75 }}>
        {t("map.read.caveat")}
      </Typography>

      <MuiLink component={RouterLink} to="/article" sx={{ fontSize: "0.76rem" }}>
        {t("map.read.full")}
      </MuiLink>
    </Box>
  );
}
