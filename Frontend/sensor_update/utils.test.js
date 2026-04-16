import { describe, it, expec, beforeEach, vi, expect } from "vitest";
import { normalizeSensorId, formatDate, parseNormalizedSensorIds, validationMessaages, loadSensorCache, saveSensorCache, mergeValidatedSensors, mergeOriginalSensorIds } from "./utils.js";

describe('normalizeSensorId', () => {
    it('normalizes inputted sensor id correctly', () => {
        // Arrange
        //const id = 'm2-3-4';
        // Act
        //result = normalizeSensorId(id);
        // Assert
        //expect(result).toBe('M002-03-004');
        expect(normalizeSensorId('m2-3-4')).toBe('M002-03-004');
        expect(normalizeSensorId('M10_20_30')).toBe('M010-20-030');
        expect(normalizeSensorId('m2-0003-0003')).toBe('M002-03-003');
    });

    it('returns null for invalid input', () => {
        expect(normalizeSensorId('bad')).toBeNull();
    });
});

describe('formatDate', () => {
    it('formats date into readable string DD/MM/YY, hh:mm:ss AM/PM format', () => {
        const d = new Date('2025-01-01T12:00:00Z');
        expect(formatDate(d)).toMatch(/\d{2}\/\d{2}\/\d{2},/);
    });
});


describe('parseNormalizedSensorIds', () => {
    it('parses and normalizes valid input correctly', () => {
        const result = parseNormalizedSensorIds("m1-2-3, M4_5_6");
        expect(result.normalizedIds).toEqual(['M001-02-003', 'M004-05-006']);
        expect(result.failed).toEqual([]);
        expect(result.normalizedMap).toEqual({
            'M001-02-003': 'm1-2-3',
            'M004-05-006': 'M4_5_6'
        });
    });

    it('returns failed items for invalid input', () => {
        const result = parseNormalizedSensorIds("bad, m1-2-3");
        expect(result.failed).toContain('bad');
        expect(result.normalizedIds).toContain('M001-02-003');
    });
});

describe('validationMessages', () => {
    it('builds correct messages from input arrays', () => {
        const result = validationMessaages({
            failed: ['bad1', 'bad2'],
            notFound: ['M001-02-003'],
            alreadyAdded: ['M004-05-006']
        });

        expect(result).toContain('Invalid syntax: bad1,bad2');
        expect(result).toContain('Not found: M001-02-003');
        expect(result).toContain('Already added: M004-05-006');
    });

    it('returns empty string if no errors', () => {
        expect(validationMessaages({})).toBe('');
    });
});


describe('saveSensorCache', () => {
    beforeEach(() => {
        const store = {};
        vi.stubGlobal('localStorage', {
            getItem: vi.fn((key) => store[key]),
            setItem: vi.fn((key, value) => { store[key] = value }),
        });
    });

    it('saves sensor cache to localStorage', () => {
        saveSensorCache(['M001-01-001'], ['M002-02-032']);
        expect(localStorage.setItem).toHaveBeenCalledOnce();
    });

    it('loads sensor cache from localStorage', () => {
        const data = {
            validated: ['M001-01-001'],
            original: ['M002-02-032']
        };
        localStorage.setItem('wafer_validated_sensors_cache', JSON.stringify(data));

        const result = loadSensorCache();
        expect(result.validated).toEqual(['M001-01-001']);
        expect(result.original).toEqual(['M002-02-032']);
    });

    it('returns null for bad JSON', () => {
        localStorage.setItem('wafer_validated_sensors_cache', 'bad-json');
        const result = loadSensorCache();
        expect(result).toBeNull();
    });
});

describe('mergeValidatedSensors', () => {
    it('merges new unique sensors only', () => {
        const existing = [{ unique_identifier: 'M003-04-034'}, { unique_identifier: 'M022-034-210'}];
        const newOnes = [{ unique_identifier: 'M003-04-034'}, {unique_identifier: 'M006-10-100'}];
        const result = mergeValidatedSensors(existing, newOnes);
        console.log(result);
        expect(result).toHaveLength(3);
        expect(result.find(s => s.unique_identifier === 'M006-10-100')).toBeTruthy();
    });
});

describe('mergeOriginalSensorIds', () => {
    it('merges unique IDs only', () => {
        const existing = ['M003-04-002', 'A034-10-200'];
        const newOnes = ['A034-10-200', 'M100-04-021'];
        const result = mergeOriginalSensorIds(existing, newOnes);
        expect(result).toEqual(['M003-04-002', 'A034-10-200', 'M100-04-021']);
    });
});