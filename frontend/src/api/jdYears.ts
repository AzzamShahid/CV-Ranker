/** Input representation is separate from the canonical numeric/null JD value. */
export function parseMinimumYears(text:string):number|null {
  const trimmed=text.trim();
  if(trimmed==='')return null;
  if(!/^(?:\d+(?:\.\d+)?|\.\d+)$/.test(trimmed))
    throw new Error('Minimum years must be a non-negative number (decimals allowed).');
  const value=Number(trimmed);
  if(!Number.isFinite(value)||value<0)
    throw new Error('Minimum years must be a finite non-negative number.');
  return value;
}
