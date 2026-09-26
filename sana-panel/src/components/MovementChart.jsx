import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

export default function MovementChart({ data }) {
  return (
    <div className="h-72 w-full" dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="colorMoving" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#14B8A6" stopOpacity={0.4} />
              <stop offset="95%" stopColor="#14B8A6" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="colorStopped" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#F59E0B" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#F59E0B" stopOpacity={0} />
            </linearGradient>
          </defs>

          <CartesianGrid strokeDasharray="3 3" stroke="#1F2D4D" />
          <XAxis
            dataKey="hour"
            stroke="#5F6E8F"
            tick={{ fill: '#9BA8C4', fontSize: 12 }}
            style={{ fontFamily: 'Vazirmatn' }}
          />
          <YAxis
            stroke="#5F6E8F"
            tick={{ fill: '#9BA8C4', fontSize: 12 }}
          />
          <Tooltip
            contentStyle={{
              background: '#16213A',
              border: '1px solid #1F2D4D',
              borderRadius: '10px',
              fontFamily: 'Vazirmatn',
              direction: 'rtl',
            }}
            labelStyle={{ color: '#E8EDF7' }}
            itemStyle={{ color: '#9BA8C4' }}
          />
          <Legend
            wrapperStyle={{ fontFamily: 'Vazirmatn', direction: 'rtl', fontSize: 12 }}
          />
          <Area
            type="monotone"
            dataKey="moving"
            name="در حال حرکت"
            stroke="#14B8A6"
            strokeWidth={2}
            fill="url(#colorMoving)"
          />
          <Area
            type="monotone"
            dataKey="stopped"
            name="متوقف"
            stroke="#F59E0B"
            strokeWidth={2}
            fill="url(#colorStopped)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
