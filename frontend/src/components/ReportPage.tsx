import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

interface DayStats {
  date: string;
  movements_total: number;
  movements_failed: number;
  avg_response_ms: number;
  p95_response_ms: number;
  slow_responses: number;
  battery_min: number;
  top_movement: string;
}

interface ProsthesisReport {
  prosthesis_id: number;
  serial_number: string;
  model: string;
  side: string;
  summary: {
    days_with_data: number;
    movements_total: number;
    recognition_rate: number;
    avg_response_ms: number;
    slow_responses_share: number;
    battery_min: number;
  };
  days: DayStats[];
}

interface Report {
  user: string;
  period: {
    date_from: string;
    date_to: string;
    processed_until: string;
    truncated: boolean;
  };
  prostheses: ProsthesisReport[];
}

const percent = (value: number) => `${(value * 100).toFixed(1)}%`;

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const downloadReport = async () => {
    if (!keycloak?.token) {
      setError('Not authenticated');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setReport(null);

      // access-токен живёт 5 минут, перед запросом обновляем его, если осталось меньше 30 секунд
      await keycloak.updateToken(30);

      const params = new URLSearchParams();
      if (dateFrom) params.set('date_from', dateFrom);
      if (dateTo) params.set('date_to', dateTo);
      const query = params.toString();

      const response = await fetch(
        `${process.env.REACT_APP_API_URL}/reports${query ? `?${query}` : ''}`,
        {
          headers: {
            'Authorization': `Bearer ${keycloak.token}`
          }
        }
      );

      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail || `Request failed with status ${response.status}`);
      }

      setReport(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const saveReport = () => {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `report_${report.user}_${report.period.date_from}_${report.period.date_to}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (!initialized) {
    return <div>Loading...</div>;
  }

  if (!keycloak.authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <button
          onClick={() => keycloak.login()}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100 py-8">
      <div className="p-8 bg-white rounded-lg shadow-md">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Usage Reports</h1>
          <div className="text-sm text-gray-600">
            {keycloak.tokenParsed?.preferred_username}
            <button onClick={() => keycloak.logout()} className="ml-3 text-blue-600 hover:underline">
              Logout
            </button>
          </div>
        </div>

        <div className="flex items-end gap-4 mb-4">
          <label className="text-sm text-gray-700">
            From
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="block mt-1 px-2 py-1 border rounded"
            />
          </label>
          <label className="text-sm text-gray-700">
            To
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="block mt-1 px-2 py-1 border rounded"
            />
          </label>
          <button
            onClick={downloadReport}
            disabled={loading}
            className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
              loading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {loading ? 'Generating Report...' : 'Download Report'}
          </button>
        </div>
        <p className="text-xs text-gray-500">Empty period means the last 7 processed days.</p>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}

        {report && (
          <div className="mt-6">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm text-gray-700">
                {report.period.date_from} .. {report.period.date_to}
              </div>
              <button onClick={saveReport} className="text-sm text-blue-600 hover:underline">
                Save as JSON
              </button>
            </div>

            {report.period.truncated && (
              <div className="mb-4 p-3 bg-yellow-100 text-yellow-800 rounded text-sm">
                Data is processed up to {report.period.processed_until}, later days are not included yet.
              </div>
            )}

            {report.prostheses.map((prosthesis) => (
              <div key={prosthesis.prosthesis_id} className="mb-6">
                <h2 className="font-semibold">
                  {prosthesis.model}, {prosthesis.side} ({prosthesis.serial_number})
                </h2>
                <p className="text-sm text-gray-600 mb-2">
                  {prosthesis.summary.movements_total} movements,
                  recognition {percent(prosthesis.summary.recognition_rate)},
                  avg response {prosthesis.summary.avg_response_ms} ms,
                  over 100 ms: {percent(prosthesis.summary.slow_responses_share)},
                  min battery {prosthesis.summary.battery_min}%
                </p>
                <table className="text-sm w-full border-collapse">
                  <thead>
                    <tr className="text-left border-b">
                      <th className="py-1 pr-4">Date</th>
                      <th className="py-1 pr-4">Movements</th>
                      <th className="py-1 pr-4">Failed</th>
                      <th className="py-1 pr-4">Avg, ms</th>
                      <th className="py-1 pr-4">p95, ms</th>
                      <th className="py-1 pr-4">&gt;100 ms</th>
                      <th className="py-1 pr-4">Min battery</th>
                      <th className="py-1">Top movement</th>
                    </tr>
                  </thead>
                  <tbody>
                    {prosthesis.days.map((day) => (
                      <tr key={day.date} className="border-b last:border-0">
                        <td className="py-1 pr-4">{day.date}</td>
                        <td className="py-1 pr-4">{day.movements_total}</td>
                        <td className="py-1 pr-4">{day.movements_failed}</td>
                        <td className="py-1 pr-4">{day.avg_response_ms}</td>
                        <td className="py-1 pr-4">{day.p95_response_ms}</td>
                        <td className="py-1 pr-4">{day.slow_responses}</td>
                        <td className="py-1 pr-4">{day.battery_min}%</td>
                        <td className="py-1">{day.top_movement}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
