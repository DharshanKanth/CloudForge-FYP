import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DiagramImportModal } from '../DiagramImportModal';

const importMock = vi.hoisted(() => vi.fn());
vi.mock('../../../services/api', () => ({
  diagramApi: { import: importMock },
}));

async function selectFile(container: HTMLElement, file: File) {
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [file] } });
  const readBtn = await screen.findByRole('button', { name: /read diagram/i });
  await waitFor(() => expect(readBtn).not.toBeDisabled());
  return readBtn;
}

describe('DiagramImportModal', () => {
  beforeEach(() => importMock.mockReset());

  it('reads a file, imports it, and applies the result', async () => {
    const onApply = vi.fn();
    const onClose = vi.fn();
    importMock.mockResolvedValue({
      data: {
        format: 'drawio',
        summary: 'Imported drawio diagram: 2 resource(s), 1 connection(s).',
        nodes: [{ id: 'vpc', data: { resourceType: 'vpc' } }],
        edges: [{ source: 'vpc', target: 'sub' }],
        recognized: 2,
        unrecognized: [],
        warnings: [],
        validation: { valid: true, issues: [] },
      },
    });
    const { container } = render(<DiagramImportModal onApply={onApply} onClose={onClose} />);
    const readBtn = await selectFile(
      container,
      new File(['<mxfile/>'], 'arch.drawio', { type: 'text/xml' }),
    );
    fireEvent.click(readBtn);

    const applyBtn = await screen.findByRole('button', { name: /apply to canvas/i });
    fireEvent.click(applyBtn);
    await waitFor(() => expect(onApply).toHaveBeenCalled());
    expect(onApply.mock.calls[0][1]).toEqual([{ source: 'vpc', target: 'sub' }]);
    expect(onClose).toHaveBeenCalled();
  });

  it('warns when nothing recognisable was found', async () => {
    importMock.mockResolvedValue({
      data: {
        format: 'mermaid',
        summary: 'Imported mermaid diagram: 0 resource(s), 0 connection(s).',
        nodes: [],
        edges: [],
        recognized: 0,
        unrecognized: [{ label: 'WAF', reason: 'Not a supported AWS resource type' }],
        warnings: ['1 element(s) were not recognised and were skipped.'],
        validation: { valid: true, issues: [] },
      },
    });
    const { container } = render(<DiagramImportModal onApply={vi.fn()} onClose={vi.fn()} />);
    const readBtn = await selectFile(container, new File(['x'], 'a.mmd'));
    fireEvent.click(readBtn);
    expect(await screen.findByText(/no supported aws resources/i)).toBeInTheDocument();
    expect(screen.getByText('WAF')).toBeInTheDocument();
  });
});
