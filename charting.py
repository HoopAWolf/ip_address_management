import matplotlib.pyplot as plt

# Dummy data: Query names and their average response times in seconds
queries = ['Dashboard Load', 'Search', 'Filter', 'Details View', 'Update']
response_times = [1.5, 1.7, 1.3, 1.9, 1.6]  # All values are below 2 seconds

plt.figure(figsize=(10, 6))
bars = plt.bar(queries, response_times, color='skyblue')

# Add a horizontal line to represent the 2-second threshold
plt.axhline(y=2, color='red', linestyle='--', label='2-second threshold')

# Annotate each bar with its response time
for bar in bars:
    height = bar.get_height()
    plt.annotate(f'{height:.1f}s',
                 xy=(bar.get_x() + bar.get_width() / 2, height),
                 xytext=(0, 3),  # 3 points vertical offset
                 textcoords="offset points",
                 ha='center', va='bottom')

plt.xlabel("Query Type")
plt.ylabel("Average Response Time (seconds)")
plt.title("Chart 3: User Interface Response Times")
plt.legend()
plt.tight_layout()

# Save the chart to an image file and display it
plt.savefig("UI_Response_Times.png")
plt.show()
