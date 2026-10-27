def show_data_quality(workspace):
    return {**workspace.quality(), 'cleaning_report': workspace.cleaning_report,
            'note': 'This report always describes the original uploaded rows. Cleaning creates a separate copy.'}
