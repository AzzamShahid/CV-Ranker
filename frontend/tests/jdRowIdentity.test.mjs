import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createEditableRow,
  rowsToEditable,
  updateRowField,
  updateRowYearText,
  removeRow,
  moveRow,
  editableToCanonical,
  hasRowValidationErrors,
  resetClientSequenceForTesting
} from '../.jdrows-test/jdRows.js';

test('DA021-Phase2: Known reproduction - deleting row 1 does not transfer 3 years to row 2', () => {
  resetClientSequenceForTesting();
  const initial = [
    { ID: 'R001', Requirement: 'Need 3y Python', Priority: 'required', Type: 'skill', 'JD source': '3y Python', 'Minimum years': 3 },
    { ID: 'R002', Requirement: 'Need 7y Arch', Priority: 'required', Type: 'experience', 'JD source': '7y Arch', 'Minimum years': 7 }
  ];
  let rows = rowsToEditable(initial);
  assert.equal(rows[0].yearText, '3');
  assert.equal(rows[1].yearText, '7');
  const key0 = rows[0]._clientKey;
  const key1 = rows[1]._clientKey;

  // Delete R001
  rows = removeRow(rows, key0);
  assert.equal(rows.length, 1);
  assert.equal(rows[0]._clientKey, key1);
  assert.equal(rows[0].ID, 'R002');
  assert.equal(rows[0].yearText, '7');

  const outgoing = editableToCanonical(rows);
  assert.equal(outgoing.length, 1);
  assert.equal(outgoing[0].ID, 'R002');
  assert.equal(outgoing[0]['Minimum years'], 7);
  assert.equal(outgoing[0]._clientKey, undefined);
  assert.equal(outgoing[0].yearText, undefined);
});

test('DA021-Phase2: Delete first, middle, and last rows preserves independent row identities', () => {
  resetClientSequenceForTesting();
  const initial = [
    { ID: 'R001', Requirement: 'One', Priority: 'required', Type: 'skill', 'JD source': 'S1', 'Minimum years': 1 },
    { ID: 'R002', Requirement: 'Two', Priority: 'required', Type: 'skill', 'JD source': 'S2', 'Minimum years': 2 },
    { ID: 'R003', Requirement: 'Three', Priority: 'required', Type: 'skill', 'JD source': 'S3', 'Minimum years': 3 },
    { ID: 'R004', Requirement: 'Four', Priority: 'required', Type: 'skill', 'JD source': 'S4', 'Minimum years': 4 },
    { ID: 'R005', Requirement: 'Five', Priority: 'required', Type: 'skill', 'JD source': 'S5', 'Minimum years': 5 }
  ];
  let rows = rowsToEditable(initial);

  // Delete middle row (R003)
  rows = removeRow(rows, rows[2]._clientKey);
  assert.deepEqual(rows.map(r => r.ID), ['R001', 'R002', 'R004', 'R005']);
  assert.deepEqual(rows.map(r => r.yearText), ['1', '2', '4', '5']);

  // Delete first row (R001)
  rows = removeRow(rows, rows[0]._clientKey);
  assert.deepEqual(rows.map(r => r.ID), ['R002', 'R004', 'R005']);
  assert.deepEqual(rows.map(r => r.yearText), ['2', '4', '5']);

  // Delete last row (R005)
  rows = removeRow(rows, rows[rows.length - 1]._clientKey);
  assert.deepEqual(rows.map(r => r.ID), ['R002', 'R004']);
  assert.deepEqual(rows.map(r => r.yearText), ['2', '4']);

  const canonical = editableToCanonical(rows);
  assert.deepEqual(canonical.map(r => r['Minimum years']), [2, 4]);
});

test('DA021-Phase2: Multiple unsaved rows with blank ID get unique client keys', () => {
  resetClientSequenceForTesting();
  const initial = [
    { ID: '', Requirement: 'Unsaved 1', Priority: 'required', Type: 'skill', 'JD source': 'S1', 'Minimum years': null },
    { ID: '', Requirement: 'Unsaved 2', Priority: 'preferred', Type: 'skill', 'JD source': 'S2', 'Minimum years': 1.5 }
  ];
  let rows = rowsToEditable(initial);
  assert.notEqual(rows[0]._clientKey, rows[1]._clientKey);
  assert.ok(rows[0]._clientKey.length > 5);
  assert.ok(rows[1]._clientKey.length > 5);

  // Add another unsaved row
  const newRow = createEditableRow({ Requirement: 'Unsaved 3', 'Minimum years': 4 });
  rows = [...rows, newRow];
  assert.equal(rows.length, 3);
  assert.notEqual(rows[2]._clientKey, rows[0]._clientKey);
  assert.notEqual(rows[2]._clientKey, rows[1]._clientKey);
  assert.equal(rows[2].yearText, '4');

  // Delete the second row
  rows = removeRow(rows, rows[1]._clientKey);
  assert.equal(rows.length, 2);
  assert.equal(rows[0].Requirement, 'Unsaved 1');
  assert.equal(rows[0].yearText, '');
  assert.equal(rows[1].Requirement, 'Unsaved 3');
  assert.equal(rows[1].yearText, '4');
});

test('DA021-Phase2: Reorder rows preserves year values and row state', () => {
  const initial = [
    { ID: 'A', Requirement: 'A req', Priority: 'required', Type: 'skill', 'JD source': 'A', 'Minimum years': 10 },
    { ID: 'B', Requirement: 'B req', Priority: 'required', Type: 'skill', 'JD source': 'B', 'Minimum years': 20 },
    { ID: 'C', Requirement: 'C req', Priority: 'required', Type: 'skill', 'JD source': 'C', 'Minimum years': 30 }
  ];
  let rows = rowsToEditable(initial);

  // Move row 0 down to index 2
  rows = moveRow(rows, 0, 2);
  assert.deepEqual(rows.map(r => r.ID), ['B', 'C', 'A']);
  assert.deepEqual(rows.map(r => r.yearText), ['20', '30', '10']);

  const canonical = editableToCanonical(rows);
  assert.deepEqual(canonical.map(r => r['Minimum years']), [20, 30, 10]);
});

test('DA021-Phase2: Decimal years, null values, and valid empty text are preserved', () => {
  let rows = [createEditableRow({ ID: 'R1', Requirement: 'Req 1', 'Minimum years': null })];
  assert.equal(rows[0].yearText, '');
  assert.equal(rows[0]['Minimum years'], null);

  // Edit to decimal years
  rows = updateRowYearText(rows, rows[0]._clientKey, '2.5');
  assert.equal(rows[0].yearText, '2.5');
  assert.equal(rows[0]['Minimum years'], 2.5);
  assert.equal(rows[0].yearError, null);

  // Clear back to empty/null
  rows = updateRowYearText(rows, rows[0]._clientKey, '   ');
  assert.equal(rows[0].yearText, '   ');
  assert.equal(rows[0]['Minimum years'], null);
  assert.equal(rows[0].yearError, null);

  const canonical = editableToCanonical(rows);
  assert.equal(canonical[0]['Minimum years'], null);
});

test('DA021-Phase2: Invalid input text stays attached to original row and rejects submission', () => {
  const initial = [
    { ID: 'R001', Requirement: 'One', Priority: 'required', Type: 'skill', 'JD source': 'S1', 'Minimum years': 3 },
    { ID: 'R002', Requirement: 'Two', Priority: 'required', Type: 'skill', 'JD source': 'S2', 'Minimum years': 5 }
  ];
  let rows = rowsToEditable(initial);

  // Type invalid text into R001
  rows = updateRowYearText(rows, rows[0]._clientKey, 'five years');
  assert.equal(rows[0].yearText, 'five years');
  assert.ok(rows[0].yearError);
  assert.equal(hasRowValidationErrors(rows), true);

  // Type valid decimal into R002
  rows = updateRowYearText(rows, rows[1]._clientKey, '4.5');
  assert.equal(rows[1].yearText, '4.5');
  assert.equal(rows[1].yearError, null);

  // Now delete R002; R001 still has its invalid text and error!
  rows = removeRow(rows, rows[1]._clientKey);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].ID, 'R001');
  assert.equal(rows[0].yearText, 'five years');
  assert.ok(rows[0].yearError);

  // Cannot produce canonical payload with invalid years
  assert.throws(() => editableToCanonical(rows), /invalid minimum years/);
});

test('DA021-Phase2: Row fields updating preserves identity and clean outgoing payload', () => {
  let rows = [createEditableRow({ ID: 'R10', Requirement: 'Old Req', Priority: 'preferred', 'Minimum years': 2 })];
  const originalKey = rows[0]._clientKey;

  rows = updateRowField(rows, originalKey, 'Requirement', 'New Requirement Text');
  rows = updateRowField(rows, originalKey, 'Priority', 'required');
  assert.equal(rows[0]._clientKey, originalKey);
  assert.equal(rows[0].Requirement, 'New Requirement Text');
  assert.equal(rows[0].Priority, 'required');
  assert.equal(rows[0].isDirty, true);

  const outgoing = editableToCanonical(rows);
  assert.equal(outgoing[0]._clientKey, undefined);
  assert.equal(outgoing[0].yearText, undefined);
  assert.equal(outgoing[0].isDirty, undefined);
  assert.equal(outgoing[0].Requirement, 'New Requirement Text');
  assert.equal(outgoing[0].Priority, 'required');
  assert.equal(outgoing[0]['Minimum years'], 2);
});
