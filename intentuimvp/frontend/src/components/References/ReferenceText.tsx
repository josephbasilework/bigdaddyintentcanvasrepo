"use client";

import { useMemo } from "react";
import type { CanvasNode } from "@/state/canvasStore";
import { buildReferenceTokens } from "@/utils/referenceLinks";
import { ReferenceLink } from "./ReferenceLink";

type ReferenceTextProps = {
  text: string;
  turnIdBySequence?: Map<number, number>;
  nodes?: CanvasNode[];
};

export const ReferenceText = ({
  text,
  turnIdBySequence,
  nodes,
}: ReferenceTextProps) => {
  const tokens = useMemo(
    () => buildReferenceTokens(text, { turnIdBySequence, nodes }),
    [nodes, text, turnIdBySequence]
  );

  return (
    <>
      {tokens.map((token, index) => {
        if (token.type === "text") {
          return (
            <span key={`ref-text-${index}`}>{token.value}</span>
          );
        }
        const href =
          token.target.type === "turn"
            ? `#turn-${token.target.id}`
            : `#node-${token.target.id}`;
        return (
          <ReferenceLink key={`ref-link-${index}`} href={href}>
            {token.value}
          </ReferenceLink>
        );
      })}
    </>
  );
};
