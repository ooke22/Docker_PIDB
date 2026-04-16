// fetcProcesses.test.js
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetcProcesses, processList } from './data-fetching.js';

// Mock the utils and url module
vi.mock('./utils.js', () => ({
  getCookie: vi.fn(() => 'mocked-csrf-token'),
  getToken: vi.fn(() => 'mocked-token'),
}));

vi.mock('./url.js', () => ({
  processIdAPI: '/mocked/processes/',
}));

describe('fetcProcesses', () => {
  beforeEach(() => {
    global.fetch = vi.fn(); // reset before each test
  });

  it('should fetch and set processList on success', async () => {
    const mockData = [{ id: 1, name: 'Process A' }, { id: 2, name: 'Process B' }];
    
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockData,
    });

    const data = await fetcProcesses();
    expect(fetch).toHaveBeenCalledWith('/mocked/processes/', {
      method: 'GET',
      headers: {
        'Authorization': 'Bearer mocked-token',
        'X-CSRFToken': 'mocked-csrf-token',
      },
    });

    expect(data).toEqual(mockData);
    expect(processList).toEqual(mockData);
  });

  it('should throw an error when response is not ok', async () => {
    fetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      text: async () => 'Internal Server Error',
    });

    await expect(fetcProcesses()).rejects.toThrow('Unable to fetch processes.');
  });

  it('should throw an error when fetch itself fails', async () => {
    fetch.mockRejectedValueOnce(new Error('Network Error'));

    await expect(fetcProcesses()).rejects.toThrow('Network Error');
  });
});
