import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

type RegistrationPoint = { date: string; registrations: number }

export default function RegistrationChart({ data }: { data: RegistrationPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
        <defs>
          <linearGradient id="registrationFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8b78ed" stopOpacity={0.23} />
            <stop offset="100%" stopColor="#8b78ed" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#252937" vertical={false} />
        <XAxis
          dataKey="date"
          tickLine={false}
          axisLine={false}
          tick={{ fill: '#697085', fontSize: 11 }}
          tickFormatter={(date: string) => date.slice(5)}
        />
        <YAxis
          allowDecimals={false}
          tickLine={false}
          axisLine={false}
          tick={{ fill: '#697085', fontSize: 11 }}
        />
        <Tooltip
          contentStyle={{
            background: '#161923',
            border: '1px solid #2b3040',
            borderRadius: 9,
            color: '#e7e9f1',
            fontSize: 12,
          }}
        />
        <Area
          type="monotone"
          dataKey="registrations"
          name="Registered"
          stroke="#9b8af4"
          strokeWidth={2.2}
          fill="url(#registrationFill)"
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
