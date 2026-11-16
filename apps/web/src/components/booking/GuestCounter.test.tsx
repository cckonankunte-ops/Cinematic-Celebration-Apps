import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import GuestCounter from './GuestCounter';

describe('GuestCounter', () => {
  it('increments adults and reports the new counts', () => {
    const onChange = vi.fn();
    render(<GuestCounter adults={2} kids={1} maxPeople={10} onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: 'Increase People (above 10 yrs)' }));
    expect(onChange).toHaveBeenLastCalledWith({ adults: 3, kids: 1 });
  });

  it('never lets adults drop below 1', () => {
    const onChange = vi.fn();
    render(<GuestCounter adults={1} kids={0} maxPeople={10} onChange={onChange} />);
    const dec = screen.getByRole('button', { name: 'Decrease People (above 10 yrs)' });
    expect(dec).toBeDisabled();
  });

  it('allows kids to reach 0 but not below', () => {
    const onChange = vi.fn();
    render(<GuestCounter adults={2} kids={0} maxPeople={10} onChange={onChange} />);
    expect(
      screen.getByRole('button', { name: 'Decrease Kids (3–10 yrs)' }),
    ).toBeDisabled();
  });

  it('warns when total guests exceed the plan cap', () => {
    render(<GuestCounter adults={8} kids={5} maxPeople={10} onChange={vi.fn()} />);
    expect(screen.getByText(/please reduce to fit this plan/i)).toBeInTheDocument();
  });
});
