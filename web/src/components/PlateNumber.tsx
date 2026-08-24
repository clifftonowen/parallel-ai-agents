import { size } from "../theme";

interface Props {
  /** Short display figure, e.g. "1.44×" or "94.5s". */
  value: string;
  /** Font size in px. The plate offsets are em-scaled, so they follow it. */
  fontSize?: number;
}

/** A display figure set as three misregistered process plates.
 *
 *  Cyan, magenta and yellow only — no black plate. The dark core is the
 *  C x M x Y multiply overlap (the inks product to near-black) and the coloured
 *  fringes are the registration drift, exactly as a real three-colour press
 *  would misregister. The `.paper` span carries the text once for assistive
 *  tech and paints the white of the sheet behind the plates; the three `.plate`
 *  spans are aria-hidden repeats.
 *
 *  This is the design system's signature treatment. It is deliberately used in
 *  one place only — the headline benchmark figures — because it stops being a
 *  signature the moment it is everywhere.
 */
export default function PlateNumber({ value, fontSize = 64 }: Props) {
  return (
    <span className="cmyk-num" style={{ fontSize, display: "inline-block" }}>
      <span className="paper">{value}</span>
      <span className="plate plate-c" aria-hidden="true">{value}</span>
      <span className="plate plate-m" aria-hidden="true">{value}</span>
      <span className="plate plate-y" aria-hidden="true">{value}</span>
    </span>
  );
}

/** The same treatment at label scale, for inline use in prose. */
export function PlateNumberInline({ value }: { value: string }) {
  return <PlateNumber value={value} fontSize={size.hero} />;
}
