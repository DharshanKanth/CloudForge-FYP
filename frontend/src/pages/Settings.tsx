import { Layout } from '../components/Layout';
import { Settings as SettingsIcon } from 'lucide-react';

export default function Settings() {
  return (
    <Layout title="Settings">
      <div className="p-6 max-w-2xl mx-auto">
        <div className="card flex flex-col items-center py-16 text-center">
          <div className="w-14 h-14 rounded-2xl bg-dark-800 flex items-center justify-center mb-4">
            <SettingsIcon className="w-7 h-7 text-dark-500" />
          </div>
          <h3 className="text-base font-semibold text-dark-300 mb-2">Settings</h3>
          <p className="text-dark-500 text-sm max-w-xs">
            Account settings, API keys, and preferences will be available in a future release.
          </p>
        </div>
      </div>
    </Layout>
  );
}
