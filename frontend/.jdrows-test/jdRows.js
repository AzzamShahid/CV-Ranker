import { parseMinimumYears } from './jdYears.js';
let clientSequence = 0;
export function resetClientSequenceForTesting() {
    clientSequence = 0;
}
export function generateClientKey(existingId) {
    clientSequence += 1;
    const base = existingId && existingId.trim() ? existingId.trim() : 'new';
    return `row-identity-${base}-${clientSequence}-${Math.random().toString(36).slice(2, 7)}`;
}
export function createEditableRow(initial) {
    const minYears = initial?.['Minimum years'];
    const text = minYears == null ? '' : String(minYears);
    return {
        _clientKey: generateClientKey(initial?.ID),
        ID: initial?.ID ?? '',
        Requirement: initial?.Requirement ?? '',
        Priority: initial?.Priority ?? 'required',
        Type: initial?.Type ?? 'skill',
        'JD source': initial?.['JD source'] ?? '',
        'Mandatory JD parts': initial?.['Mandatory JD parts'],
        'Alternative groups JSON': initial?.['Alternative groups JSON'],
        'Complete JD expression JSON': initial?.['Complete JD expression JSON'],
        'Minimum years': minYears ?? null,
        'Degree level': initial?.['Degree level'],
        'Field of study': initial?.['Field of study'],
        'Evidence standard': initial?.['Evidence standard'],
        'Duration subject': initial?.['Duration subject'],
        yearText: text,
        yearError: null,
        isDirty: false,
    };
}
export function rowsToEditable(rows) {
    return rows.map(r => createEditableRow(r));
}
export function updateRowField(rows, clientKey, field, value) {
    return rows.map(row => {
        if (row._clientKey !== clientKey)
            return row;
        return {
            ...row,
            [field]: value,
            isDirty: true,
        };
    });
}
export function updateRowYearText(rows, clientKey, text) {
    return rows.map(row => {
        if (row._clientKey !== clientKey)
            return row;
        let parsed = null;
        let error = null;
        try {
            parsed = parseMinimumYears(text);
        }
        catch (e) {
            error = e instanceof Error ? e.message : 'Invalid years input';
        }
        return {
            ...row,
            yearText: text,
            yearError: error,
            'Minimum years': error ? row['Minimum years'] : parsed,
            isDirty: true,
        };
    });
}
export function removeRow(rows, clientKey) {
    return rows.filter(row => row._clientKey !== clientKey);
}
export function moveRow(rows, fromIndex, toIndex) {
    if (fromIndex < 0 || fromIndex >= rows.length || toIndex < 0 || toIndex >= rows.length) {
        return rows;
    }
    const next = [...rows];
    const [removed] = next.splice(fromIndex, 1);
    next.splice(toIndex, 0, removed);
    return next;
}
export function hasRowValidationErrors(rows) {
    return rows.some(r => r.yearError !== null);
}
export function editableToCanonical(rows) {
    return rows.map(row => {
        let finalYears = null;
        try {
            finalYears = parseMinimumYears(row.yearText);
        }
        catch {
            throw new Error(`Requirement ${row.ID || row.Requirement || 'criterion'} has invalid minimum years: "${row.yearText}".`);
        }
        return {
            ID: row.ID,
            Requirement: row.Requirement,
            Priority: row.Priority,
            Type: row.Type,
            'JD source': row['JD source'],
            'Mandatory JD parts': row['Mandatory JD parts'],
            'Alternative groups JSON': row['Alternative groups JSON'],
            'Complete JD expression JSON': row['Complete JD expression JSON'],
            'Minimum years': finalYears,
            'Degree level': row['Degree level'],
            'Field of study': row['Field of study'],
            'Evidence standard': row['Evidence standard'],
            'Duration subject': row['Duration subject'],
        };
    });
}
