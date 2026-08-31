import { Component } from 'react';
import Button from './Button';

// A failed page chunk or renderer must not remove navigation and sign-out.
// Recovery is explicit: never replay an experiment or other mutation.
export default class PageBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <section role="alert" className="rounded-lg border border-amber-300 bg-amber-50 p-6 text-gray-900">
        <h2 className="text-lg font-semibold">This page could not be displayed</h2>
        <p className="mt-2 text-sm">No automatic retry will be attempted. If you submitted a job, inspect its status after reconnecting before repeating it.</p>
        <p className="mt-2 text-sm">Reloading clears this tab’s credential and unsaved input. You will need to sign in again.</p>
        <Button type="button" className="mt-4" onClick={() => window.location.reload()}>
          Reload and sign in again
        </Button>
      </section>
    );
  }
}
