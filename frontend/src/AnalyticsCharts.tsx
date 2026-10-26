import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from 'recharts'

const colors = ['#a296f2', '#62c9a1', '#79afe7', '#e3ad68', '#cf83b7']
type StoragePoint = { date: string; storage_bytes: number }
type FileTypePoint = { name: string; value: number }

export function StorageTrend({ data }: { data: StoragePoint[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 9, right: 4, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="storageFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#6ea9db" stopOpacity={0.23} />
            <stop offset="100%" stopColor="#6ea9db" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#252937" vertical={false} />
        <XAxis
          dataKey="date"
          tickLine={false}
          axisLine={false}
          tick={{ fill: '#697085', fontSize: 9 }}
          tickFormatter={(date: string) => date.slice(5)}
          interval="preserveStartEnd"
        />
        <Tooltip
          formatter={(value) => [
            `${(Number(value) / 1024).toFixed(1)} KB`,
            'Stored artwork',
          ]}
          contentStyle={{
            background: '#161923',
            border: '1px solid #2b3040',
            borderRadius: 9,
            color: '#e7e9f1',
            fontSize: 11,
          }}
        />
        <Area
          type="monotone"
          dataKey="storage_bytes"
          name="Storage"
          stroke="#79afe7"
          strokeWidth={2}
          fill="url(#storageFill)"
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export function FileTypeDonut({ data }: { data: FileTypePoint[] }) {
  return (
    <div className="filetype-viz">
      <div className="filetype-donut">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius="70%"
              outerRadius="94%"
              paddingAngle={4}
              stroke="none"
              cornerRadius={3}
            >
              {data.map((entry, index) => (
                <Cell key={entry.name} fill={colors[index % colors.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: '#161923',
                border: '1px solid #2b3040',
                borderRadius: 9,
                color: '#e7e9f1',
                fontSize: 11,
              }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="donut-center">
          <strong>{data.reduce((sum, item) => sum + item.value, 0)}</strong>
          <span>assets</span>
        </div>
      </div>
      <div className="filetype-legend">
        {data.map((item, index) => (
          <div key={item.name}>
            <i style={{ background: colors[index % colors.length] }} />
            <span>{item.name}</span>
            <b>{item.value}</b>
          </div>
        ))}
      </div>
    </div>
  )
}
