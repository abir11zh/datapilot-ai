import plotly.express as px
import pandas as pd


class ChartService:
    @staticmethod
    def style(fig):
        fig.update_layout(template='plotly_white', margin=dict(l=25, r=20, t=20, b=45),
                          paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                          font=dict(family='Segoe UI, Arial, sans-serif', size=12, color='#606b80'),
                          colorway=['#5B5CEB', '#24a28b', '#9c8aeb', '#e7ab55', '#528ccb'],
                          hoverlabel=dict(bgcolor='#182033', font_color='white'),
                          bargap=.28, height=350, title=None, legend=dict(orientation='h', y=-.2))
        fig.update_xaxes(gridcolor='#eef0f6', zeroline=False, title_font_size=12)
        fig.update_yaxes(gridcolor='#eef0f6', zeroline=False, title_font_size=12)
        return fig

    def create_chart(self, df, kind='bar', x=None, y=None, title=None):
        if df is None or df.empty or x not in df or (kind != 'histogram' and y not in df):
            return None
        if kind not in {'bar', 'line', 'scatter', 'pie', 'histogram'}:
            return None
        if kind != 'histogram' and not pd.api.types.is_numeric_dtype(df[y]):
            return None
        if kind == 'pie' and ((df[y].dropna() < 0).any() or df[y].sum() <= 0):
            return None
        try:
            if kind == 'pie':
                fig = px.pie(df.head(30), names=x, values=y, title=title, hole=.55)
            elif kind == 'bar' and (x in {'Country', 'Description'} or df[x].astype(str).str.len().max() > 22):
                sample = df.head(20)
                fig = px.bar(sample, x=y, y=x, orientation='h', title=title, color_discrete_sequence=['#6964e6'])
                fig.update_yaxes(categoryorder='total ascending', tickmode='array', tickvals=sample[x].tolist(),
                                 ticktext=[str(v)[:28] + ('…' if len(str(v)) > 28 else '') for v in sample[x]])
            else:
                if kind == 'bar' and pd.api.types.is_datetime64_any_dtype(df[x]):
                    df = df.copy()
                    df[x] = df[x].dt.strftime('%Y-%m-%d')
                fig = getattr(px, kind)(df.head(1000), x=x, **({'y': y} if kind != 'histogram' else {}), title=title,
                                         color_discrete_sequence=['#5b63ef', '#32bfa1', '#ffb65c'])
            if kind == 'line':
                fig.update_traces(mode='lines+markers')
                if len(df) == 1:
                    fig.update_xaxes(tickmode='array', tickvals=df[x].tolist(),
                                     ticktext=[str(value)[:10] for value in df[x]])
            return self.style(fig)
        except (ValueError, TypeError):
            return None

    def bar_chart(self, df, x_col, y_col, title=None):
        return self.create_chart(df, 'bar', x_col, y_col, title)

    def line_chart(self, df, x_col, y_col, title=None):
        return self.create_chart(df, 'line', x_col, y_col, title)

    def scatter_chart(self, df, x_col, y_col, title=None):
        return self.create_chart(df, 'scatter', x_col, y_col, title)
